#C:/Users/r.zribi/AppData/Local/anaconda3/Scripts/activate

# Prérequis:
#   install streamlit pandas matplotlib seaborn requests numpy
#   ollama pull gpt-oss:20b (sur Orion le transférer depusi un autre PC)
#  
#   
#
# Lancer:
#  python -m streamlit run viz_streamlit.py


import io
import json
import re
import traceback
from typing import Any, Dict, List, Tuple, Optional

import numpy as np
import pandas as pd
import requests
import matplotlib.pyplot as plt
import seaborn as sns
import streamlit as st



# CONFIG

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434/v1"
DEFAULT_MODEL = "gpt-oss:20b:cloud"
DEFAULT_TEMPERATURE = 0.0



# Gestion du dataset

def flatten_json(obj: Dict[str, Any], parent: str = "", sep: str = "_") -> Dict[str, Any]:
    items = {}
    for k, v in obj.items():
        new_key = f"{parent}{sep}{k}" if parent else k
        if isinstance(v, dict):
            items.update(flatten_json(v, new_key, sep=sep))
        else:
            items[new_key] = v
    return items


def load_jsonl_bytes(data: bytes, sample_rows: int = 5000) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    # JSONL = 1 JSON par ligne
    for i, raw_line in enumerate(data.splitlines()):
        if i >= sample_rows:
            break
        line = raw_line.decode("utf-8", errors="ignore").strip()
        if not line:
            continue
        obj = json.loads(line)
        rows.append(flatten_json(obj))
    df = pd.DataFrame(rows)
    df.columns = df.columns.str.strip()
    return df


def load_csv_bytes(data: bytes) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(data))


def sanitize_nested_cols(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert list/dict values into JSON strings so pandas ops (nunique, etc.) won't crash.
    """
    out = df.copy()
    for c in out.columns:
        s = out[c].dropna()
        if s.empty:
            continue
        sample = s.head(50)
        if sample.apply(lambda v: isinstance(v, (list, dict))).any():
            out[c] = out[c].apply(
                lambda v: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
            )
    return out



# Schema + light que l'ancienne version qui tournait sur le même modèle mais en cloud

def build_light_schema(df: pd.DataFrame, sample_n: int = 800) -> Dict[str, Dict[str, Any]]:
    """
    Schema léger:
    - missing_ratio exact (colonne entière)
    - nunique_approx sur sample
    - is_numeric sur sample
    - is_time_like par nom + regex sur sample (sans pd.to_datetime => pas de warnings)
    """
    n = len(df)
    df_s = df.sample(n=min(sample_n, n), random_state=42) if n > sample_n else df

    schema: Dict[str, Dict[str, Any]] = {}

    for c in df.columns:
        s_full = df[c]
        s = df_s[c]

        missing_ratio = float(s_full.isna().mean())
        nunique_approx = int(s.dropna().astype(str).nunique())

        sn = pd.to_numeric(s, errors="coerce")
        is_numeric = bool(sn.notna().sum() >= max(3, int(0.3 * sn.shape[0])))

        cl = c.lower()
        is_time_like = ("time" in cl) or ("date" in cl) or ("timestamp" in cl)
        if not is_time_like:
            sample_txt = s.dropna().astype(str).head(30)
            if not sample_txt.empty:
                looks_date = sample_txt.str.contains(r"\d{4}-\d{2}-\d{2}", regex=True).sum()
                looks_time = sample_txt.str.contains(r"\d{2}:\d{2}:\d{2}", regex=True).sum()
                if (looks_date + looks_time) >= 5:
                    is_time_like = True

        schema[c] = {
            "dtype": str(s_full.dtype),
            "missing_ratio": missing_ratio,
            "nunique_approx": nunique_approx,
            "is_numeric": is_numeric,
            "is_time_like": is_time_like,
        }

    return schema


def pick_candidates_from_schema(schema: Dict[str, Dict[str, Any]], max_each: int = 25) -> Tuple[List[str], List[str], List[str]]:
    cat, num, time = [], [], []
    for col, meta in schema.items():
        if meta.get("missing_ratio", 0.0) > 0.99:
            continue

        if meta.get("is_time_like"):
            time.append(col)
            continue

        if meta.get("is_numeric"):
            num.append(col)
            continue

        if meta.get("nunique_approx", 10**9) <= 100:
            cat.append(col)

    return cat[:max_each], num[:max_each], time[:max_each]



# Appel Ollama

SYSTEM_PROMPT = """You are a data visualization code generator.
Return ONLY Python code (no explanations, no markdown, no backticks).
DO NOT write any import statements.
Use pandas DataFrame `df` already loaded.
Use seaborn as sns and matplotlib.pyplot as plt (already available).
Always call plt.tight_layout(). Do NOT call plt.show().

Rules:
- If user asks for count by category -> use groupby().size() or value_counts(), then bar/count plot.
- For distribution of categories -> seaborn countplot.
- For relationship between two numeric columns -> seaborn scatterplot.
- For trend over time -> sort by x, then seaborn lineplot.
- If user mentions a filter (col = value), apply df = df[df[col] == value] before plotting.
"""

def ollama_chat(base_url: str, model: str, system: str, user: str, temperature: float = 0.0) -> str:
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": float(temperature),
    }
    r = requests.post(url, json=payload, timeout=300)
    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:1500]}")
    return r.json()["choices"][0]["message"]["content"]


def extract_python_code(txt: str) -> str:
    m = re.search(r"```python(.*?)```", txt, flags=re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(r"```(.*?)```", txt, flags=re.DOTALL)
    if m:
        return m.group(1).strip()
    return txt.strip()


def strip_import_lines(code: str) -> str:
    lines = []
    for line in code.splitlines():
        if re.match(r"^\s*(import|from)\s+\w+", line):
            continue
        lines.append(line)
    return "\n".join(lines)


SAFE_BUILTINS = {
    "len": len, "range": range, "min": min, "max": max, "sum": sum,
    "print": print, "sorted": sorted, "list": list, "dict": dict, "set": set,
    "enumerate": enumerate, "zip": zip, "abs": abs,
    "str": str, "int": int, "float": float, "bool": bool, "round": round,
    "map": map, "filter": filter, "any": any, "all": all
}


def exec_code_to_png(code: str, df: pd.DataFrame) -> Tuple[Optional[bytes], Optional[str]]:
    
    # Execute le code génére et capture la fig MPL actuel en png bytes
    
    #Returns (png_bytes, traceback_str).
    
    plt.close("all")

    safe_globals = {
        "__builtins__": SAFE_BUILTINS,
        "pd": pd,
        "np": np,
        "sns": sns,
        "plt": plt,
        "df": df,
    }

    try:
        exec(code, safe_globals, {})
        fig = plt.gcf()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", dpi=200)
        buf.seek(0)
        return buf.read(), None
    except Exception:
        return None, traceback.format_exc()


def generate_chart(df: pd.DataFrame, question: str, base_url: str, model: str, temperature: float,
                   sample_n_schema: int, max_each_candidates: int) -> Dict[str, Any]:
    df = sanitize_nested_cols(df)

    schema = build_light_schema(df, sample_n=sample_n_schema)
    cat_cols, num_cols, time_cols = pick_candidates_from_schema(schema, max_each=max_each_candidates)

    all_columns = list(df.columns)

    user_prompt = f"""
ALL COLUMNS:
{all_columns}

CANDIDATE COLUMNS (auto-detected from a light schema):
- categorical_cols: {cat_cols}
- numeric_cols: {num_cols}
- time_cols: {time_cols}

USER QUESTION:
{question}

Rules:
- Use ONLY columns from ALL COLUMNS.
- Prefer using the candidate lists.
- Return ONLY Python code.
""".strip()

    raw = ollama_chat(base_url=base_url, model=model, system=SYSTEM_PROMPT, user=user_prompt, temperature=temperature)
    code = strip_import_lines(extract_python_code(raw))

    png_bytes, tb = exec_code_to_png(code, df)

    return {
        "candidate_cols": {"categorical": cat_cols, "numeric": num_cols, "time": time_cols},
        "code": code,
        "png_bytes": png_bytes,
        "error": tb,
        "raw_model_output": raw,
    }



# STREAMLIT UI

st.set_page_config(page_title="LLM Viz (Light)", layout="wide")

st.title("LLM Viz — Version Light")
st.caption("")

with st.sidebar:
    st.subheader("Connexion LLM")
    base_url = st.text_input("Ollama base URL", value=DEFAULT_OLLAMA_BASE_URL)
    model_name = st.text_input("Model", value=DEFAULT_MODEL)
    temperature = st.slider("Temperature", 0.0, 0.9, float(DEFAULT_TEMPERATURE), 0.05)

    st.subheader("Données")
    #sample_rows_jsonl = st.number_input("sample des colonnes JSON", min_value=100, max_value=500000, value=50000, step=1000)
    sample_rows_jsonl = 50000
    sample_n_schema = st.number_input("Nombre de lignes pour sample du schema", min_value=100, max_value=20000, value=800, step=100)
    max_each_candidates = st.number_input("Max de colonnes candidates", min_value=10, max_value=200, value=25, step=5)

    st.subheader("Affichage")
    show_raw = st.checkbox("Afficher la réponse brute du modèle", value=False)
    show_schema = st.checkbox("Afficher colonnes candidates", value=True)
    show_columns = st.checkbox("Montrer toutes les colonnes", value=False)


col_left, col_right = st.columns([1.0, 1.2], gap="large")

with col_left:
    st.subheader("1) Upload")
    uploaded = st.file_uploader("CSV ou JSONL", type=["csv", "jsonl", "log", "txt"])
    df: Optional[pd.DataFrame] = None
    file_info = None

    if uploaded is not None:
        data_bytes = uploaded.getvalue()
        name = uploaded.name.lower()
        file_info = (uploaded.name, len(data_bytes))

        try:
            if name.endswith(".csv"):
                df = load_csv_bytes(data_bytes)
            else:
                df = load_jsonl_bytes(data_bytes, sample_rows=int(sample_rows_jsonl))
            st.success(f"Loaded {uploaded.name} — shape: {df.shape}")
        except Exception as e:
            st.error(f"Echec de chargement du fichier: {e}")
            df = None

    if df is not None and show_columns:
        with st.expander("Colonness"):
            st.write(list(df.columns))

with col_right:
    st.subheader("2) Prompt")
    default_prompt = "Ecrivez votre prompt"
    question = st.text_area("Question (FR)", value=default_prompt, height=120)

    cta_col1, cta_col2 = st.columns([1, 1])
    with cta_col1:
        run_btn = st.button("Générer", type="primary", use_container_width=True, disabled=(df is None))
    with cta_col2:
        st.button("Reset", use_container_width=True, on_click=lambda: st.session_state.clear())

    if run_btn and df is not None:
        with st.spinner("Génération du code + exécution..."):
            try:
                result = generate_chart(
                    df=df,
                    question=question,
                    base_url=base_url,
                    model=model_name,
                    temperature=float(temperature),
                    sample_n_schema=int(sample_n_schema),
                    max_each_candidates=int(max_each_candidates),
                )
            except Exception as e:
                st.error(f"Echec de l'appel au llm: {e}")
                result = {"error": traceback.format_exc(), "code": "", "png_bytes": None, "candidate_cols": None, "raw_model_output": ""}

        if result.get("candidate_cols") and show_schema:
            with st.expander("Colonnes candidates (cat / num / time)", expanded=False):
                st.write(result["candidate_cols"])

        if result.get("error"):
            st.error("Erreur d'execution")
            with st.expander("Traceback", expanded=True):
                st.code(result["error"], language="text")

        if result.get("png_bytes"):
            st.subheader("3) Graphe")
            st.image(result["png_bytes"],width= 1200)

        st.subheader("4) Code généré")
        st.code(result.get("code", ""), language="python")

        if show_raw:
            with st.expander("Output"):
                st.code(result.get("raw_model_output", ""), language="text")

    st.divider()
    st.caption("Température = 0 conseillé + Éviter les prompts trop longs." )