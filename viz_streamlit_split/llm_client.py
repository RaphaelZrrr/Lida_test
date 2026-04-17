import re

import requests


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