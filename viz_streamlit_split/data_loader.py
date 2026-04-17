import io
import json
from typing import Any, Dict, List

import pandas as pd


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