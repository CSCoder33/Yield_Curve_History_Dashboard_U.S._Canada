import os
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from .utils import ensure_dir


def load_raw_series(raw_paths: Dict[str, str]) -> Dict[str, pd.DataFrame]:
    frames = {}
    for name, path in raw_paths.items():
        df = pd.read_csv(path)
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        frames[name] = df
    return frames


def merge_series(frames: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    out = None
    for name, df in frames.items():
        d = df.rename(columns={"value": name})[["date", name]].copy()
        if out is None:
            out = d
        else:
            out = out.merge(d, on="date", how="outer")
    out.sort_values("date", inplace=True)
    out.drop_duplicates(subset=["date"], keep="last", inplace=True)
    return out


def forward_fill_yields(df: pd.DataFrame, yield_cols: List[str]) -> pd.DataFrame:
    d = df.copy()
    d[yield_cols] = d[yield_cols].ffill()
    return d


def compute_slopes(df: pd.DataFrame, mapping: Dict[str, Dict[float, str]]) -> pd.DataFrame:
    d = df.copy()
    # mapping: {"US": {2: 'US_2Y', 10: 'US_10Y', 5: 'US_5Y', 30: 'US_30Y'}, ...}
    for ccy, tenor_map in mapping.items():
        def have(col: str) -> bool:
            return col in d.columns
        if 10 in tenor_map and 2 in tenor_map and have(tenor_map[10]) and have(tenor_map[2]):
            d[f"{ccy}_2s10s"] = d[tenor_map[10]] - d[tenor_map[2]]
        if 30 in tenor_map and 5 in tenor_map and have(tenor_map[30]) and have(tenor_map[5]):
            d[f"{ccy}_5s30s"] = d[tenor_map[30]] - d[tenor_map[5]]
    return d


def compute_changes_bp(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    d = df.copy()
    d = d.set_index("date")
    out = pd.DataFrame(index=d.index)
    # Daily change
    for col in cols:
        out[(col, "1d")] = (d[col] - d[col].shift(1)) * 100
        out[(col, "1w")] = (d[col] - d[col].shift(5)) * 100
        out[(col, "1m")] = (d[col] - d[col].shift(21)) * 100
        out[(col, "3m")] = (d[col] - d[col].shift(63)) * 100
    out.columns = pd.MultiIndex.from_tuples(out.columns, names=["series", "bucket"])
    out.reset_index(inplace=True)
    return out


def compute_rolling_vol_bp(df: pd.DataFrame, cols: List[str], window: int = 20) -> pd.DataFrame:
    d = df.copy().set_index("date")
    out = pd.DataFrame(index=d.index)
    daily_chg = d[cols].diff() * 100
    # Allow shorter history to still produce a value
    minp = max(5, window // 4)
    vol = daily_chg.rolling(window=window, min_periods=minp).std()
    for c in cols:
        out[c] = vol[c]
    out.reset_index(inplace=True)
    return out


def compute_cross_country_spread(df: pd.DataFrame, us_10y: str, ca_10y: str) -> pd.DataFrame:
    d = df.copy()
    if us_10y in d.columns and ca_10y in d.columns:
        d["UST10_minus_GoC10_bp"] = (d[us_10y] - d[ca_10y]) * 100
    return d


def save_processed(df_levels: pd.DataFrame, out_dir: str) -> Tuple[str, str]:
    ensure_dir(out_dir)
    parquet_path = os.path.join(out_dir, "daily.parquet")
    csv_path = os.path.join(out_dir, "daily.csv")
    df_levels.to_parquet(parquet_path, index=False)
    df_levels.to_csv(csv_path, index=False)
    return parquet_path, csv_path
