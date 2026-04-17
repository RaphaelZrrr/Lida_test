from typing import Any, Dict

import pandas as pd

from code_executor import exec_code_to_png
from config import SYSTEM_PROMPT
from data_loader import sanitize_nested_cols
from llm_client import extract_python_code, ollama_chat, strip_import_lines
from schema_utils import pick_candidates_from_schema, build_light_schema


def generate_chart(
    df: pd.DataFrame,
    question: str,
    base_url: str,
    model: str,
    temperature: float,
    sample_n_schema: int,
    max_each_candidates: int,
) -> Dict[str, Any]:
    df = sanitize_nested_cols(df)

    schema = build_light_schema(df, sample_n=sample_n_schema)
    cat_cols, num_cols, time_cols = pick_candidates_from_schema(
        schema, max_each=max_each_candidates
    )

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

    raw = ollama_chat(
        base_url=base_url,
        model=model,
        system=SYSTEM_PROMPT,
        user=user_prompt,
        temperature=temperature,
    )
    code = strip_import_lines(extract_python_code(raw))

    png_bytes, tb = exec_code_to_png(code, df)

    return {
        "candidate_cols": {"categorical": cat_cols, "numeric": num_cols, "time": time_cols},
        "code": code,
        "png_bytes": png_bytes,
        "error": tb,
        "raw_model_output": raw,
    }