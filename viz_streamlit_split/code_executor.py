import io
import traceback
from typing import Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


SAFE_BUILTINS = {
    "len": len,
    "range": range,
    "min": min,
    "max": max,
    "sum": sum,
    "print": print,
    "sorted": sorted,
    "list": list,
    "dict": dict,
    "set": set,
    "enumerate": enumerate,
    "zip": zip,
    "abs": abs,
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "round": round,
    "map": map,
    "filter": filter,
    "any": any,
    "all": all,
}


def exec_code_to_png(code: str, df: pd.DataFrame) -> Tuple[Optional[bytes], Optional[str]]:
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