from typing import Any, Dict, List, Tuple

import pandas as pd


from typing import Any, Dict
import pandas as pd


def build_categorical_examples(df: pd.DataFrame, categorical_cols: list[str], max_values: int = 8) -> dict:
    examples = {}
    for col in categorical_cols:
        vals = (
            df[col]
            .dropna()
            .astype(str)
            .value_counts()
            .head(max_values)
            .index
            .tolist()
        )
        examples[col] = vals
    return examples


def build_light_schema(df: pd.DataFrame, sample_n: int = 800) -> Dict[str, Dict[str, Any]]:
    n = len(df)
    df_s = df.sample(n=min(sample_n, n), random_state=42) if n > sample_n else df

    schema: Dict[str, Dict[str, Any]] = {}

    ignored_exact_names = {"contacts", "sensors", "weapons"}

    for c in df.columns:
        s_full = df[c]
        s = df_s[c]

        missing_ratio = float(s_full.isna().mean())
        nunique_approx = int(s.dropna().astype(str).nunique())

        cl = c.lower()

        # 1) ignored columns
        is_ignored = cl in ignored_exact_names

        # 2) time-like detection
        is_time_like = ("time" in cl) or ("date" in cl) or ("timestamp" in cl)
        if not is_time_like:
            sample_txt = s.dropna().astype(str).head(30)
            if not sample_txt.empty:
                looks_date = sample_txt.str.contains(r"\d{4}-\d{2}-\d{2}", regex=True).sum()
                looks_time = sample_txt.str.contains(r"\d{2}:\d{2}:\d{2}", regex=True).sum()
                if (looks_date + looks_time) >= 5:
                    is_time_like = True

        # 3) identifier detection
        is_identifier = any(x in cl for x in ["identifier", "instance"]) or cl.endswith("_id")

        # 4) boolean detection
        is_boolean = False
        non_null = s.dropna()

        if pd.api.types.is_bool_dtype(s_full):
            is_boolean = True
        elif not non_null.empty:
            unique_vals = set(non_null.astype(str).str.strip().str.lower().unique())
            if unique_vals and unique_vals.issubset({"true", "false", "0", "1"}):
                is_boolean = True

        # 5) numeric detection
        # only if not boolean / not time-like / not ignored / not identifier
        is_numeric = False
        if not is_boolean and not is_time_like and not is_ignored and not is_identifier:
            sn = pd.to_numeric(s, errors="coerce")
            is_numeric = bool(sn.notna().sum() >= max(3, int(0.3 * sn.shape[0])))

        schema[c] = {
            "dtype": str(s_full.dtype),
            "missing_ratio": missing_ratio,
            "nunique_approx": nunique_approx,
            "is_numeric": is_numeric,
            "is_time_like": is_time_like,
            "is_boolean": is_boolean,
            "is_identifier": is_identifier,
            "is_ignored": is_ignored,
        }

    return schema


from typing import Any, Dict, List, Tuple


def pick_candidates_from_schema(
    schema: Dict[str, Dict[str, Any]], max_each: int = 25
) -> Tuple[List[str], List[str], List[str]]:
    cat, num, time = [], [], []

    for col, meta in schema.items():
        if meta.get("missing_ratio", 0.0) > 0.99:
            continue

        if meta.get("is_ignored"):
            continue

        if meta.get("is_time_like"):
            time.append(col)
            continue

        if meta.get("is_identifier"):
            continue

        if meta.get("is_boolean"):
            cat.append(col)
            continue

        if meta.get("is_numeric"):
            if meta.get("nunique_approx", 10**9) <= 20:
                cat.append(col)
            else:
                num.append(col)
            continue

        if meta.get("nunique_approx", 10**9) <= 100:
            cat.append(col)

    return cat[:max_each], num[:max_each], time[:max_each]