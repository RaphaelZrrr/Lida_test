# Notebook blocks — LIDA + Ollama Mistral 7B

Colle les blocs ci-dessous dans des cellules séparées (Alt+Entrée).

## Bloc 1 — Imports

```python
import base64
import json
import re
from pathlib import Path
from typing import Any, Dict, List

import matplotlib.pyplot as plt
import pandas as pd
from lida import Manager, llm
from openai import OpenAI
```

## Bloc 2 — Configuration

```python
MODEL = "mistral:7b"
BASE_URL = "http://localhost:11434/v1"

MAPPER_SYSTEM = """
You are a data-visualization mapper.
Given a dataframe schema and a user prompt, return JSON only with this exact structure:
{
  "chart": "auto"|"bar"|"line"|"scatter"|"hist"|"pie",
  "x": string|null,
  "y": string|null,
  "group_by": string|null,
  "aggregate": "count"|"mean"|"median"|"sum"|"min"|"max"|null,
  "filters": [{"column": string, "op": "=="|"!="|">"|">="|"<"|"<=", "value": any}],
  "reasoning": string
}
Rules:
- Use only columns from schema.
- If unsure, use null and chart="auto".
- Output valid JSON only.
""".strip()
```

## Bloc 3 — Chargement data + schema

```python
def flatten_record(obj: Dict[str, Any], parent: str = "") -> Dict[str, Any]:
    flat: Dict[str, Any] = {}
    for key, value in obj.items():
        full_key = f"{parent}_{key}" if parent else key
        if isinstance(value, dict):
            flat.update(flatten_record(value, full_key))
        elif isinstance(value, list):
            continue
        else:
            flat[full_key] = value
    return flat


def load_df(file_path: str) -> pd.DataFrame:
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".csv":
        return pd.read_csv(path)

    if suffix in {".json", ".log"}:
        rows = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                payload = line.strip()
                if payload:
                    rows.append(flatten_record(json.loads(payload)))
        return pd.DataFrame(rows)

    raise ValueError(f"Unsupported format: {suffix}")


def build_schema(df: pd.DataFrame, max_cols: int = 80):
    out = []
    for col in df.columns[:max_cols]:
        s = df[col]
        out.append({
            "name": col,
            "dtype": str(s.dtype),
            "sample_values": s.dropna().astype(str).head(3).tolist(),
        })
    return out
```

## Bloc 4 — Mapping prompt -> colonnes

```python
def parse_json_object_loose(text: str) -> Dict[str, Any]:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found")
    return json.loads(cleaned[start:end + 1])


def llm_map_columns(prompt: str, schema: List[Dict[str, Any]]) -> Dict[str, Any]:
    client = OpenAI(api_key="ollama", base_url=BASE_URL)
    message = (
        f"SCHEMA:\n{json.dumps(schema, ensure_ascii=False)}\n\n"
        f"PROMPT:\n{prompt}\n\nReturn JSON only."
    )

    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": MAPPER_SYSTEM},
            {"role": "user", "content": message},
        ],
        temperature=0.1,
    )

    content = resp.choices[0].message.content or "{}"
    try:
        return parse_json_object_loose(content)
    except Exception:
        return {
            "chart": "auto",
            "x": None,
            "y": None,
            "group_by": None,
            "aggregate": "count",
            "filters": [],
            "reasoning": "fallback_invalid_json",
        }


def sanitize_mapping(mapping: Dict[str, Any], df: pd.DataFrame) -> Dict[str, Any]:
    columns = set(df.columns)
    out = dict(mapping)

    for key in ["x", "y", "group_by"]:
        if out.get(key) not in columns:
            out[key] = None

    if out.get("aggregate") not in {"count", "mean", "median", "sum", "min", "max", None}:
        out["aggregate"] = "count"

    if (out.get("chart") or "auto").lower() not in {"auto", "bar", "line", "scatter", "hist", "pie"}:
        out["chart"] = "auto"
    else:
        out["chart"] = (out.get("chart") or "auto").lower()

    clean_filters = []
    for flt in out.get("filters", []):
        col, op, val = flt.get("column"), flt.get("op"), flt.get("value")
        if col in columns and op in {"==", "!=", ">", ">=", "<", "<="}:
            clean_filters.append({"column": col, "op": op, "value": val})
    out["filters"] = clean_filters

    return out
```

## Bloc 5 — Goal + LIDA run

```python
def build_goal(prompt: str, mapping: Dict[str, Any]) -> Dict[str, Any]:
    instructions = []
    chart = mapping.get("chart", "auto")
    if chart == "auto":
        instructions.append("Choose the most appropriate chart using matplotlib.")
    else:
        instructions.append(f"Use a {chart} chart using matplotlib.")

    if mapping.get("group_by"):
        instructions.append(f"Group by '{mapping['group_by']}'.")
    if mapping.get("x"):
        instructions.append(f"Use x='{mapping['x']}'.")
    if mapping.get("y"):
        instructions.append(f"Use y='{mapping['y']}'.")

    instructions.append(f"Aggregation preference: {mapping.get('aggregate') or 'count'}.")

    if mapping.get("filters"):
        instructions.append("Apply filters:")
        for flt in mapping["filters"]:
            instructions.append(f"- {flt['column']} {flt['op']} {flt['value']}")

    return {
        "question": prompt,
        "visualization": "\n".join(instructions),
        "rationale": mapping.get("reasoning", "mapping from local LLM"),
    }


def reduce_df_for_lida(df: pd.DataFrame, mapping: Dict[str, Any], max_extra_numeric: int = 3) -> pd.DataFrame:
    keep = []
    for key in ["group_by", "x", "y"]:
        col = mapping.get(key)
        if col and col in df.columns and col not in keep:
            keep.append(col)

    for flt in mapping.get("filters", []):
        col = flt.get("column")
        if col and col in df.columns and col not in keep:
            keep.append(col)

    numeric = df.select_dtypes(include="number").columns.tolist()
    for col in numeric:
        if col not in keep:
            keep.append(col)
        if len([x for x in keep if x in numeric]) >= max_extra_numeric:
            break

    if not keep:
        keep = df.columns[: min(10, len(df.columns))].tolist()

    return df[keep].copy()


def save_chart_png(chart_obj: Any, out_path: Path):
    raster = getattr(chart_obj, "raster", None)
    if isinstance(raster, str) and raster:
        if raster.startswith("data:image"):
            out_path.write_bytes(base64.b64decode(raster.split(",", 1)[1]))
            return
        try:
            out_path.write_bytes(base64.b64decode(raster))
            return
        except Exception:
            pass

    fig = getattr(chart_obj, "figure", None)
    if fig is not None:
        fig.savefig(out_path, dpi=150, bbox_inches="tight")
        return

    raise RuntimeError("Unable to save LIDA chart output")


def build_text_generator(model: str, base_url: str):
    """Compat helper for LIDA/llmx versions (`api_base` vs `base_url`)."""
    try:
        return llm("openai", model=model, base_url=base_url, api_key="ollama")
    except TypeError:
        return llm("openai", model=model, api_key="ollama")


def run_lida_visualizer(file: str, prompt: str, out: str = "out.png"):
    df = load_df(file)
    schema = build_schema(df)
    mapping = sanitize_mapping(llm_map_columns(prompt, schema), df)

    reduced = reduce_df_for_lida(df, mapping)
    tmp = Path("tmp_lida.csv")
    reduced.to_csv(tmp, index=False)

    text_gen = build_text_generator(model=MODEL, base_url=BASE_URL)
    manager = Manager(text_gen=text_gen)

    summary = manager.summarize(str(tmp))
    goal = build_goal(prompt, mapping)
    charts = manager.visualize(summary=summary, goal=goal, library="matplotlib")
    if not charts:
        raise RuntimeError("No chart returned by LIDA")

    save_chart_png(charts[0], Path(out))
    return {
        "mapping": mapping,
        "goal": goal,
        "out": out,
        "chart_code": getattr(charts[0], "code", None),
    }
```

## Bloc 6 — Exécution

```python
result = run_lida_visualizer(
    file="data/lidata.log",
    prompt="Répartition des entités par ForceIdentifier",
    out="out_lida.png",
)
result
```

## Bloc 7 — Prompt alternatif

```python
result = run_lida_visualizer(
    file="data/lidata.log",
    prompt="Moyenne de SimTime par ForceIdentifier",
    out="out_lida_mean.png",
)
result
```
