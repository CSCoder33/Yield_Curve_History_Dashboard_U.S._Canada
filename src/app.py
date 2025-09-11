import os
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd
import streamlit as st

# Ensure project root is on path so we can import `src.*` when run directly
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils import read_yaml
from src.viz import curve_snapshot, slope_trackers, tenor_change_heatmaps, vol_strip, xccy_spread


st.set_page_config(page_title="UST vs GoC Curves", layout="wide")

@st.cache_data(show_spinner=False)
def load_data(version: float):
    """Load processed data; cache invalidates when file mtime (version) changes."""
    df = None
    parquet_path = "data/processed/daily.parquet"
    csv_path = "data/processed/daily.csv"
    if os.path.exists(parquet_path):
        df = pd.read_parquet(parquet_path)
    elif os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
    if df is not None:
        df["date"] = pd.to_datetime(df["date"])  # ensure datetime
    return df


def main():
    series_cfg = read_yaml("config/series.yaml")
    viz_cfg = read_yaml("config/viz.yaml")
    countries_cfg = read_yaml("config/countries.yaml")
    # Determine a cache-busting version based on processed file mtime
    parquet_path = "data/processed/daily.parquet"
    csv_path = "data/processed/daily.csv"
    mtime = None
    if os.path.exists(parquet_path):
        mtime = os.path.getmtime(parquet_path)
    elif os.path.exists(csv_path):
        mtime = os.path.getmtime(csv_path)
    df = load_data(mtime or 0.0)
    if df is None or df.empty:
        st.error("No processed data found. Run pipeline first.")
        return

    # Sidebar
    st.sidebar.header("Filters")
    if st.sidebar.button("Refresh data"):
        st.cache_data.clear()
        st.rerun()
    ccys = st.sidebar.multiselect("Countries", ["US", "CA"], default=["US", "CA"])
    compare_windows = st.sidebar.multiselect("Compare windows", viz_cfg["lookbacks"]["compare_curves"], default=viz_cfg["lookbacks"]["compare_curves"])
    tenors = sorted(list(set([float(c["tenor_years"]) for _, c in series_cfg.items() if c.get("tenor_years")])))
    tenor_sel = st.sidebar.multiselect("Tenors (years)", tenors, default=tenors)
    # Date selection
    dmin, dmax = df["date"].min(), df["date"].max()
    curve_date = st.sidebar.slider("Curve date", min_value=dmin.to_pydatetime(), max_value=dmax.to_pydatetime(), value=dmax.to_pydatetime())

    # Tabs
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Curves", "Slopes", "Tenor Changes", "Vol", "Cross-Country", "One-Pager"])

    with tab1:
        st.subheader("Curve Snapshot")
        # Limit series_cfg by selected countries and tenors
        series_cfg_view = {k: v for k, v in series_cfg.items() if (v.get("country") in ccys) and (not v.get("tenor_years") or float(v["tenor_years"]) in set(tenor_sel))}
        fig = curve_snapshot(df.copy(), series_cfg_view, {**viz_cfg, "lookbacks": {**viz_cfg["lookbacks"], "compare_curves": compare_windows}}, countries_cfg, pd.to_datetime(curve_date))
        st.pyplot(fig)

    with tab2:
        st.subheader("Curvature & Steepness Over Time")
        fig = slope_trackers(df.copy(), viz_cfg)
        st.pyplot(fig)

    with tab3:
        st.subheader("Tenor Change Heatmaps")
        figs = tenor_change_heatmaps(df.copy(), series_cfg, viz_cfg)
        cols = st.columns(2)
        for i, (country, fig) in enumerate(figs.items()):
            cols[i % 2].pyplot(fig)

    with tab4:
        st.subheader("Volatility Strip (Rolling 20d)")
        fig = vol_strip(df.copy(), series_cfg, viz_cfg)
        st.pyplot(fig)

    with tab5:
        st.subheader("UST10 – GoC10 Spread")
        fig = xccy_spread(df.copy(), viz_cfg)
        st.pyplot(fig)

    with tab6:
        st.subheader("One-Pager")
        img_path = os.path.join(viz_cfg["export"]["one_pager_dir"], "one_pager_latest.png")
        if os.path.exists(img_path):
            st.image(img_path, width='stretch')
            with open(img_path, "rb") as f:
                st.download_button("Download One-Pager PNG", f, file_name=os.path.basename(img_path))
        else:
            st.info("Run pipeline to generate the one-pager.")

    # Footer note and timestamp
    st.caption("Note: 1w/1m/3m = 5/21/63 trading days")
    # Reuse mtime computed earlier
    ts = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M") if mtime else "N/A"
    st.caption(f"Last updated: {ts}")


if __name__ == "__main__":
    main()
