from typing import Any, Dict, List, Tuple

import pandas as pd


def build_light_schema(df: pd.DataFrame, sample_n: int = 800) -> Dict[str, Dict[str, Any]]:
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


def pick_candidates_from_schema(
    schema: Dict[str, Dict[str, Any]], max_each: int = 25
) -> Tuple[List[str], List[str], List[str]]:
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