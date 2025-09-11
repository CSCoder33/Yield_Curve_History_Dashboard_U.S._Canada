import os
from datetime import datetime
from typing import Dict, Tuple

import pandas as pd
import requests
import io

from .utils import ensure_dir, today_str


def fred_fetch_csv(series_id: str, start: str = "1990-01-01") -> pd.DataFrame:
    # FRED CSV endpoint for daily series; no API key required for basic CSV
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}&cosd={start}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text))
    df.rename(columns={df.columns[0]: "date", series_id: "value"}, inplace=True)
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df


def boc_valet_fetch(series_id: str, start: str = "1990-01-01") -> pd.DataFrame:
    # BoC Valet JSON observations endpoint
    # Use content negotiation (Accept: application/json). Avoid '/json' path which 404s for some series.
    base = f"https://www.bankofcanada.ca/valet/observations/{series_id}"
    headers = {"Accept": "application/json"}
    params = {"start_date": start}
    resp = requests.get(base, params=params, headers=headers, timeout=30)
    if resp.status_code >= 400:
        # Fallback: fetch a large recent window (about ~15y of business days)
        resp = requests.get(base, params={"recent": 5000}, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    obs = data.get("observations", [])
    rows = []
    for r in obs:
        d = r.get("d")
        vobj = r.get(series_id, {})
        v = vobj.get("v")
        rows.append({"date": d, "value": None if v in (None, "") else float(v)})
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


def yahoo_fx_fetch(ticker: str, start: str = "2010-01-01") -> pd.DataFrame:
    # Use stooq CSV as a no-auth fallback compatible with many tickers
    # Yahoo direct is not documented for CSV; for offline demo, this is optional.
    # We'll leave this as a stub to be replaced if desired.
    raise NotImplementedError("FX fetch not implemented in offline demo")


def fetch_series(series_cfg: Dict, raw_dir: str, start: str = "1990-01-01") -> Tuple[str, pd.DataFrame]:
    source = series_cfg["source"].lower()
    sid = series_cfg["id"]
    name = series_cfg["name"]
    dt = today_str()
    ensure_dir(raw_dir)
    out_path = os.path.join(raw_dir, f"{source}_{name}_{dt}.csv")

    if source == "fred":
        df = fred_fetch_csv(sid, start)
    elif source == "boc":
        df = boc_valet_fetch(sid, start)
    elif source == "yahoo":
        # Optional; can be implemented later
        raise NotImplementedError("Yahoo FX fetch not implemented")
    else:
        raise ValueError(f"Unknown source: {source}")

    df = df[["date", "value"]]
    df.to_csv(out_path, index=False)
    return out_path, df
