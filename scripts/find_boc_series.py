import json
import os
import re
import sys
from typing import Any, Dict, Iterable, List, Tuple


def load_json(path: str) -> Any:
    with open(path, "r") as f:
        return json.load(f)


def iter_series(records: Any) -> Iterable[Tuple[str, Dict[str, Any]]]:
    """Yield (series_id, metadata) pairs from various Valet list JSON shapes."""
    if isinstance(records, dict):
        # Common shapes: {'series': {id: meta, ...}} or {'series': [ { 'id': id, ...}, ... ]}
        ser = records.get("series")
        if isinstance(ser, dict):
            for sid, meta in ser.items():
                yield sid, meta if isinstance(meta, dict) else {"_": meta}
        elif isinstance(ser, list):
            for item in ser:
                if isinstance(item, dict):
                    sid = item.get("id") or item.get("series_id") or item.get("series") or item.get("name")
                    if sid:
                        yield str(sid), item
        # Fallback: top-level might already be {id: meta}
        else:
            for k, v in records.items():
                if isinstance(v, dict) and any(isinstance(x, (str, int, float)) for x in v.values()):
                    # Heuristic: 6+ digit V-codes
                    if re.fullmatch(r"V\d{4,}", str(k)):
                        yield str(k), v


def text_of(meta: Dict[str, Any]) -> str:
    fields = []
    for key in ("label", "title", "description", "name", "en", "fr"):
        val = meta.get(key)
        if isinstance(val, str):
            fields.append(val)
        elif isinstance(val, dict):
            if isinstance(val.get("en"), str):
                fields.append(val["en"])
    return " | ".join(fields).lower()


def match_targets(series: Iterable[Tuple[str, Dict[str, Any]]]) -> Dict[str, List[Tuple[str, str]]]:
    targets = {
        "2y": [r"2\s*-?\s*year", r"2y"],
        "5y": [r"5\s*-?\s*year", r"5y"],
        "10y": [r"10\s*-?\s*year", r"10y"],
        "30y": [r"30\s*-?\s*year|long(\s|-)?term", r"30y"],
        # 3-month T-bill
        "3m": [r"3\s*-?\s*month", r"3m", r"91\s*-?\s*day"],
    }
    # Accept either 'Government of Canada' OR 'T-bill' context, and 'yield' somewhere
    ctx_any = [r"government of canada", r"t-?bill", r"treasury bill"]
    require = r"yield"
    out: Dict[str, List[Tuple[str, str]]] = {k: [] for k in targets}
    for sid, meta in series:
        t = text_of(meta)
        if not t:
            continue
        if not (any(re.search(p, t) for p in ctx_any) and re.search(require, t)):
            continue  # need GoC or T-bill context and the word 'yield'
        for key, pats in targets.items():
            if any(re.search(p, t) for p in pats):
                out[key].append((sid, t))
    return out


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/find_boc_series.py /path/to/series_list.json")
        sys.exit(1)
    path = sys.argv[1]
    if not os.path.exists(path):
        print("File not found:", path)
        sys.exit(1)
    data = load_json(path)
    matches = match_targets(iter_series(data))
    print("Candidate BoC Valet series IDs (based on text match):\n")
    for key in ("3m", "2y", "5y", "10y", "30y"):
        rows = matches.get(key) or []
        if not rows:
            print(f"{key}: no matches found")
            continue
        print(f"{key}:")
        for sid, txt in rows[:5]:
            print(f"  {sid}  |  {txt[:100]}")


if __name__ == "__main__":
    main()
