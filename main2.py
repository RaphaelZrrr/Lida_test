"""Projet de visualisation piloté par LIDA avec Ollama (Mistral 7B local).

Usage CLI:
    python main2.py --file data/lidata.log --prompt "Répartition des entités par ForceIdentifier" --out out.png

Prérequis:
- Ollama lancé localement
- Modèle dispo, ex: `ollama pull mistral:7b`
- Dépendances python: lida, openai, pandas, matplotlib
"""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib.pyplot as plt
import pandas as pd
from lida import Manager, llm
from openai import OpenAI


DEFAULT_MODEL = "mistral:7b"
DEFAULT_BASE_URL = "http://localhost:11434/v1"


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


GOOD_PROMPTS = [
    "Répartition des entités par ForceIdentifier",
    "Pie chart des DamageState",
    "Moyenne de SimTime par ForceIdentifier",
    "Scatter Spatial_static_WorldLocation_x vs Spatial_static_WorldLocation_y",
    "Nombre d'entités par EntityType avec ForceIdentifier == 2",
]


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
        rows: List[Dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                payload = line.strip()
                if not payload:
                    continue
                rows.append(flatten_record(json.loads(payload)))
        return pd.DataFrame(rows)

    raise ValueError(f"Unsupported format: {suffix}")


def build_schema(df: pd.DataFrame, max_cols: int = 80) -> List[Dict[str, Any]]:
    schema: List[Dict[str, Any]] = []
    for col in df.columns[:max_cols]:
        series = df[col]
        non_null = series.dropna()
        dtype = str(series.dtype)
        samples = non_null.astype(str).head(3).tolist()
        schema.append({"name": col, "dtype": dtype, "sample_values": samples})
    return schema


def parse_json_object_loose(text: str) -> Dict[str, Any]:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found")
    return json.loads(cleaned[start : end + 1])


def llm_map_columns(prompt: str, schema: List[Dict[str, Any]], model: str, base_url: str) -> Dict[str, Any]:
    client = OpenAI(api_key="ollama", base_url=base_url)
    message = (
        f"SCHEMA:\n{json.dumps(schema, ensure_ascii=False)}\n\n"
        f"PROMPT:\n{prompt}\n\n"
        "Return JSON only."
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": MAPPER_SYSTEM},
            {"role": "user", "content": message},
        ],
        temperature=0.1,
    )

    content = response.choices[0].message.content or "{}"
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
        value = out.get(key)
        if value not in columns:
            out[key] = None

    valid_aggs = {"count", "mean", "median", "sum", "min", "max", None}
    if out.get("aggregate") not in valid_aggs:
        out["aggregate"] = "count"

    valid_charts = {"auto", "bar", "line", "scatter", "hist", "pie"}
    chart = (out.get("chart") or "auto").lower()
    out["chart"] = chart if chart in valid_charts else "auto"

    filters = out.get("filters") or []
    clean_filters: List[Dict[str, Any]] = []
    for flt in filters:
        col = flt.get("column")
        op = flt.get("op")
        val = flt.get("value")
        if col in columns and op in {"==", "!=", ">", ">=", "<", "<="}:
            clean_filters.append({"column": col, "op": op, "value": val})
    out["filters"] = clean_filters

    if out["x"] is None and out["group_by"] is None and len(df.columns) > 0:
        out["group_by"] = df.columns[0]

    return out


def build_goal(prompt: str, mapping: Dict[str, Any]) -> Dict[str, Any]:
    chart = mapping.get("chart", "auto")
    x = mapping.get("x")
    y = mapping.get("y")
    group_by = mapping.get("group_by")
    aggregate = mapping.get("aggregate") or "count"
    filters = mapping.get("filters") or []

    instructions: List[str] = []
    if chart == "auto":
        instructions.append("Choose the most appropriate chart using matplotlib.")
    else:
        instructions.append(f"Use a {chart} chart using matplotlib.")

    if group_by:
        instructions.append(f"Group by '{group_by}'.")
    if x:
        instructions.append(f"Use x='{x}'.")
    if y:
        instructions.append(f"Use y='{y}'.")
    instructions.append(f"Aggregation preference: {aggregate}.")

    if filters:
        instructions.append("Apply filters:")
        for flt in filters:
            instructions.append(f"- {flt['column']} {flt['op']} {flt['value']}")

    return {
        "question": prompt,
        "visualization": "\n".join(instructions),
        "rationale": mapping.get("reasoning", "mapping from local LLM"),
    }


def reduce_df_for_lida(df: pd.DataFrame, mapping: Dict[str, Any], max_extra_numeric: int = 3) -> pd.DataFrame:
    keep: List[str] = []
    for key in ["group_by", "x", "y"]:
        col = mapping.get(key)
        if col and col not in keep and col in df.columns:
            keep.append(col)

    for flt in mapping.get("filters", []):
        col = flt.get("column")
        if col and col in df.columns and col not in keep:
            keep.append(col)

    numeric = df.select_dtypes(include="number").columns.tolist()
    for col in numeric:
        if col not in keep:
            keep.append(col)
        if len([c for c in keep if c in numeric]) >= max_extra_numeric:
            break

    if not keep:
        keep = df.columns[: min(10, len(df.columns))].tolist()

    return df[keep].copy()


def save_chart_png(chart_obj: Any, out_path: Path) -> None:
    raster = getattr(chart_obj, "raster", None)
    if isinstance(raster, str) and raster:
        if raster.startswith("data:image"):
            b64 = raster.split(",", 1)[1]
            out_path.write_bytes(base64.b64decode(b64))
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

    code = getattr(chart_obj, "code", None)
    if isinstance(code, str) and "plt" in code:
        namespace: Dict[str, Any] = {"pd": pd, "plt": plt}
        exec(code, namespace, namespace)
        maybe = namespace.get("chart")
        if hasattr(maybe, "savefig"):
            maybe.savefig(out_path, dpi=150, bbox_inches="tight")
            return

    raise RuntimeError("Unable to save LIDA chart output.")




def build_text_generator(model: str, base_url: str):
    """Compat helper for LIDA/llmx versions (`api_base` vs `base_url`)."""
    try:
        return llm("openai", model=model, base_url=base_url, api_key="ollama")
    except TypeError:
        return llm("openai", model=model, api_key="ollama")


def run_lida_visualizer(
    file: str,
    prompt: str,
    out: str = "out.png",
    model: str = DEFAULT_MODEL,
    base_url: str = DEFAULT_BASE_URL,
) -> Dict[str, Any]:
    df = load_df(file)
    schema = build_schema(df)
    mapping_raw = llm_map_columns(prompt, schema, model=model, base_url=base_url)
    mapping = sanitize_mapping(mapping_raw, df)

    reduced = reduce_df_for_lida(df, mapping)
    tmp_path = Path("tmp_lida.csv")
    reduced.to_csv(tmp_path, index=False)

    text_gen = build_text_generator(model=model, base_url=base_url)
    manager = Manager(text_gen=text_gen)

    summary = manager.summarize(str(tmp_path))
    goal = build_goal(prompt, mapping)
    charts = manager.visualize(summary=summary, goal=goal, library="matplotlib")

    if not charts:
        raise RuntimeError("LIDA did not return any chart.")

    out_path = Path(out)
    save_chart_png(charts[0], out_path)

    return {
        "out": str(out_path),
        "mapping": mapping,
        "goal": goal,
        "chart_code": getattr(charts[0], "code", None),
    }

# Notebook usage:
# from main2 import run_lida_visualizer
# run_lida_visualizer(file="data/lidata.log", prompt="Répartition des entités par ForceIdentifier", out="out.png")
