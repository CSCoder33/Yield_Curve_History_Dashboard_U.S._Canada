import os
import sys
import glob
from pathlib import Path
from datetime import datetime

import pandas as pd

# Ensure project root is on sys.path so `src` is importable when run as a script
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils import read_yaml, ensure_dir, today_str, stamp_last_updated
from src.data_fetch import fetch_series
from src.process import (
    load_raw_series, merge_series, forward_fill_yields, compute_slopes,
    compute_changes_bp, compute_rolling_vol_bp, compute_cross_country_spread, save_processed
)
from src.viz import render_and_export_all, one_pager


RAW_DIR = "data/raw"
PROC_DIR = "data/processed"


def get_or_fetch(series_cfg: dict, offline: bool, start: str = None):
    # Allow overriding start date via env for speed, default to 2010 for quicker initial pull
    if start is None:
        start = os.environ.get("START_DATE", "2010-01-01")
    skip_ca = os.environ.get("SKIP_CA", "0") == "1"
    skip_us = os.environ.get("SKIP_US", "0") == "1"
    skip_fx = os.environ.get("SKIP_FX", "0") == "1"
    raw_paths = {}
    if offline:
        # Use most recent sample files for each series
        for name, c in series_cfg.items():
            if skip_ca and c.get("country") == "CA":
                continue
            if skip_us and c.get("country") == "US":
                continue
            if skip_fx and c.get("country") == "FX":
                continue
            name = c["name"]
            pattern = os.path.join(RAW_DIR, "sample", f"*_{name}_*.csv")
            files = sorted(glob.glob(pattern))
            if not files:
                continue
            raw_paths[name] = files[-1]
        return raw_paths

    # Online: fetch if today's file not present
    ensure_dir(RAW_DIR)
    continue_on_error = os.environ.get("CONTINUE_ON_FETCH_ERROR", "0") == "1"
    for _, c in series_cfg.items():
        if skip_ca and c.get("country") == "CA":
            continue
        if skip_us and c.get("country") == "US":
            continue
        if skip_fx and c.get("country") == "FX":
            continue
        name = c["name"]
        source = c["source"]
        today = today_str()
        existing = glob.glob(os.path.join(RAW_DIR, f"{source}_{name}_{today}.csv"))
        if existing:
            raw_paths[name] = existing[0]
            continue
        try:
            path, _ = fetch_series(c, RAW_DIR, start)
            raw_paths[name] = path
        except Exception as e:
            msg = f"Failed fetching {name} from {source}: {e}"
            if continue_on_error:
                print("WARN:", msg, "-- skipping this series")
                continue
            else:
                raise RuntimeError(msg)
    return raw_paths


def main():
    series_cfg = read_yaml("config/series.yaml")
    viz_cfg = read_yaml("config/viz.yaml")
    countries_cfg = read_yaml("config/countries.yaml")
    offline = os.environ.get("OFFLINE", "0") == "1"

    raw_paths = get_or_fetch(series_cfg, offline)
    if not raw_paths:
        # Fallback: if processed exists, reuse it to render figures
        proc_csv = os.path.join(PROC_DIR, "daily.csv")
        proc_parquet = os.path.join(PROC_DIR, "daily.parquet")
        if os.path.exists(proc_parquet) or os.path.exists(proc_csv):
            if os.path.exists(proc_parquet):
                levels = pd.read_parquet(proc_parquet)
            else:
                levels = pd.read_csv(proc_csv)
            render_and_export_all(levels, series_cfg, viz_cfg, countries_cfg)
            one_pager(levels, series_cfg, viz_cfg, countries_cfg)
            stamp_last_updated("README.md", today_str())
            print("Rendered figures from existing processed dataset.")
            return
        raise SystemExit("No raw or processed data available. Provide sample data or enable network fetch.")

    frames = load_raw_series(raw_paths)
    levels = merge_series(frames)

    # Identify yield series (exclude FX)
    yield_cols = [c["name"] for _, c in series_cfg.items() if c.get("units") == "pct"]
    levels = forward_fill_yields(levels, [c for c in levels.columns if c in yield_cols])

    # Slopes mapping
    mapping = {"US": {}, "CA": {}}
    for _, c in series_cfg.items():
        if c.get("country") in ("US", "CA") and c.get("tenor_years"):
            mapping[c["country"]][int(float(c["tenor_years"]))] = c["name"]
    levels = compute_slopes(levels, mapping)
    # Rename slope columns to country-prefixed for plotting consistency
    if "US_2s10s" not in levels.columns and "US_2s10s" in [f"US_2s10s"]:
        pass  # naming already fits compute_slopes output

    # Cross-country spread in bp (only if both columns exist)
    us10 = series_cfg["US_10Y"]["name"] if "US_10Y" in series_cfg else mapping["US"].get(10)
    ca10 = series_cfg["CA_10Y"]["name"] if "CA_10Y" in series_cfg else mapping["CA"].get(10)
    if us10 and ca10 and (us10 in levels.columns) and (ca10 in levels.columns):
        levels = compute_cross_country_spread(levels, us10, ca10)

    # Save processed
    ensure_dir(PROC_DIR)
    parquet_path, csv_path = save_processed(levels, PROC_DIR)

    # Render figures
    render_and_export_all(levels, series_cfg, viz_cfg, countries_cfg)
    one_pager(levels, series_cfg, viz_cfg, countries_cfg)

    # Stamp README
    stamp_last_updated("README.md", today_str())
    print("Pipeline complete. Processed:", parquet_path)


if __name__ == "__main__":
    main()
