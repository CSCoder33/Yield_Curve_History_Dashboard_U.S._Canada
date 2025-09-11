import os
from datetime import timedelta
from typing import List, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.colors as mcolors
import seaborn as sns

from .utils import ensure_dir, read_yaml, today_str
from .process import compute_changes_bp, compute_rolling_vol_bp


def _save_figure(fig: plt.Figure, base_name: str, out_dir: str, save_png: bool, save_svg: bool):
    ensure_dir(out_dir)
    today = today_str()
    dated = os.path.join(out_dir, f"{base_name}_{today}")
    latest = os.path.join(out_dir, f"{base_name}_latest")
    if save_png:
        fig.savefig(dated + ".png", bbox_inches="tight")
        fig.savefig(latest + ".png", bbox_inches="tight")
    if save_svg:
        fig.savefig(dated + ".svg", bbox_inches="tight")
        fig.savefig(latest + ".svg", bbox_inches="tight")


def _nearest_on_or_before(d: pd.Series, target_date: pd.Timestamp) -> pd.Timestamp:
    d = pd.to_datetime(d)
    s = d[d <= target_date]
    if s.empty:
        return d.min()
    return s.max()


def curve_snapshot(df: pd.DataFrame, series_cfg: dict, viz_cfg: dict, countries_cfg: dict, curve_date: pd.Timestamp = None):
    lookbacks = viz_cfg["lookbacks"]["compare_curves"]
    colors = viz_cfg["colors"]
    style = viz_cfg["style"]

    # Map country -> list of (tenor_years, column)
    country_map = {"US": [], "CA": []}
    # Only include series that actually exist in the dataframe to avoid KeyErrors
    available_cols = set(df.columns)
    for name, c in series_cfg.items():
        if c.get("country") in ("US", "CA") and c.get("tenor_years"):
            col = c["name"]
            if col in available_cols:
                country_map[c["country"]].append((float(c["tenor_years"]), col))
    for k in country_map:
        country_map[k].sort(key=lambda x: x[0])

    d = df.copy()
    d["date"] = pd.to_datetime(d["date"])  # ensure TS
    if curve_date is None:
        curve_date = d["date"].max()

    fig, ax = plt.subplots(figsize=tuple(style["figure_sizes"]["curve_snapshot"]))
    for country, series in country_map.items():
        if not series:
            continue  # skip countries with no data
        tenors = [t for t, _ in series]
        cols = [col for _, col in series]
        # Today
        row_date = _nearest_on_or_before(d["date"], curve_date)
        # Guard: only use columns present (redundant but safe)
        cols_present = [c for c in cols if c in d.columns]
        if not cols_present:
            continue
        row = d.loc[d["date"] == row_date, cols_present]
        if not row.empty:
            ax.plot(tenors, row.values.flatten(), label=f"{country} Today", color=colors["us" if country == "US" else "ca"], linewidth=2.5)
            # endpoint label
            try:
                ax.text(tenors[-1], float(row.values.flatten()[-1]), f"{country} {int(tenors[-1])}Y {row.values.flatten()[-1]:.2f}%", color=colors["us" if country == "US" else "ca"], fontsize=style["font_size"]) 
            except Exception:
                pass
        # history lines
        for lb in lookbacks:
            if lb.endswith("M"):
                months = int(lb[:-1])
                approx_days = int(round(months * 21))
            elif lb.endswith("Y"):
                years = int(lb[:-1])
                approx_days = years * 252
            else:
                continue
            target_date = curve_date - pd.Timedelta(days=approx_days)
            tdate = _nearest_on_or_before(d["date"], target_date)
            rowh = d.loc[d["date"] == tdate, cols_present]
            if not rowh.empty:
                ax.plot(tenors, rowh.values.flatten(), color=colors["us" if country == "US" else "ca"], alpha=0.35, linewidth=1.5, label=f"{country} {lb} ago")

    ax.set_title("US vs Canada Yield Curves — Today vs Prior Dates", fontsize=style["title_size"])
    ax.set_xlabel("Tenor (years)", fontsize=style["font_size"])
    ax.set_ylabel("Yield (%)", fontsize=style["font_size"])
    ax.grid(True, alpha=0.2)
    ax.legend(ncol=2, fontsize=style["font_size"])
    return fig


def slope_trackers(df: pd.DataFrame, viz_cfg: dict):
    style = viz_cfg["style"]
    colors = viz_cfg["colors"]
    fig, axes = plt.subplots(2, 2, figsize=tuple(style["figure_sizes"]["slopes"]))
    pairs = [("US_2s10s", colors["us"]), ("US_5s30s", colors["us"]), ("CA_2s10s", colors["ca"]), ("CA_5s30s", colors["ca"]) ]
    titles = ["US 2s10s", "US 5s30s", "CA 2s10s", "CA 5s30s"]
    for ax, (col, color), title in zip(axes.flatten(), pairs, titles):
        if col in df.columns:
            ts_all = pd.to_datetime(df["date"]) 
            end = ts_all.max()
            start = end - pd.Timedelta(days=5*365)  # last 5 years
            mask = ts_all >= start
            ts = ts_all[mask]
            vals_bp = (df.loc[mask, col]) * 100.0
            ax.plot(ts, vals_bp, color=color, linewidth=1.5)
            ax.axhline(0, color="black", linewidth=1, alpha=0.6)
            # annotate extremes last 3y
            last3y = ts >= (ts.max() - pd.Timedelta(days=3*365))
            subset = df.loc[df["date"].isin(ts[last3y]), ["date", col]].dropna()
            if len(subset) > 0:
                idxmin = subset[col].idxmin(); idxmax = subset[col].idxmax()
                ax.scatter(pd.to_datetime(subset.loc[idxmin, "date"]), subset.loc[idxmin, col]*100.0, color=color, s=15)
                ax.scatter(pd.to_datetime(subset.loc[idxmax, "date"]), subset.loc[idxmax, col]*100.0, color=color, s=15)
        # Yearly ticks and limits over last 5y
        ax.set_xlim(start, end)
        ax.xaxis.set_major_locator(mdates.YearLocator(base=1))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
        for label in ax.get_xticklabels():
            label.set_rotation(45)
            label.set_ha('right')
        ax.set_title(title)
        ax.set_ylabel("bp")
        ax.grid(True, alpha=0.2)
    fig.suptitle("Curvature & Steepness Over Time (positive = normal, negative = inverted)", fontsize=style["title_size"])
    fig.tight_layout(rect=[0, 0.03, 1, 0.95])
    return fig


def tenor_change_heatmaps(df: pd.DataFrame, series_cfg: dict, viz_cfg: dict):
    style = viz_cfg["style"]
    colors = viz_cfg["colors"]
    # Identify tenor columns per country
    tenors_by_ccy = {"US": [], "CA": []}
    for name, c in series_cfg.items():
        if c.get("country") in ("US", "CA") and c.get("tenor_years") and c["name"] in df.columns:
            tenors_by_ccy[c["country"]].append((float(c["tenor_years"]), c["name"]))
    for k in tenors_by_ccy: tenors_by_ccy[k].sort(key=lambda x: x[0])

    figs = {}
    for country, lst in tenors_by_ccy.items():
        cols = [col for _, col in lst]
        if not cols:
            continue
        changes = compute_changes_bp(df[["date"] + cols].copy(), cols)
        # Pivot for latest row
        latest = changes["date"].max()
        ch = changes.loc[changes["date"] == latest].drop(columns=["date"])
        ch = ch.T.reset_index()
        ch.columns = ["series", "bucket", "value"]
        tenor_map = dict(lst)
        ch["tenor"] = ch["series"].map({v: k for k, v in {t: s for t, s in lst}.items()})
        heat = ch.pivot(index="bucket", columns="tenor", values="value")
        # Keep only buckets that actually have data (exclude 1d per request)
        desired = ["1w", "1m", "3m"]
        have = [b for b in desired if b in heat.index and not heat.loc[b].isna().all()]
        heat = heat.reindex(index=have)

        fig, ax = plt.subplots(figsize=tuple(style["figure_sizes"]["heatmap"]))
        # Build custom bi-color map: negatives = greys, 0 = white, positives = blue/red
        if country == "US":
            pos_colors = ["#dbe9ff", "#7fb3ff", "#1f77b4"]  # light to dark blue
        else:
            pos_colors = ["#ffd6d6", "#ff7f7f", "#d62728"]  # light to dark red
        neg_colors = ["#e6e6e6", "#bdbdbd", "#4d4d4d"]     # light to dark grey
        # Combine: dark grey -> light grey -> white -> light pos -> dark pos
        cmap = mcolors.LinearSegmentedColormap.from_list(
            f"bi_{country.lower()}",
            [neg_colors[-1], neg_colors[1], "#ffffff", pos_colors[0], pos_colors[-1]], N=256
        )
        vmax = np.nanmax(np.abs(heat.values)) if heat.size else 1
        if not np.isfinite(vmax) or vmax == 0:
            vmax = 1
        sns.heatmap(heat, cmap=cmap, vmin=-vmax, vmax=vmax, center=0, annot=True, fmt=".1f", cbar_kws={"label": "bp"}, ax=ax)
        limited = set(desired) - set(have)
        subtitle = " — limited history" if limited else ""
        ax.set_title(f"{country} Tenor Changes (bp){subtitle}")
        ax.set_xlabel("Tenor (years)")
        ax.set_ylabel("")
        figs[country] = fig
    return figs


def vol_strip(df: pd.DataFrame, series_cfg: dict, viz_cfg: dict):
    style = viz_cfg["style"]
    colors = viz_cfg["colors"]
    # Identify tenors
    tenors_by_ccy = {"US": [], "CA": []}
    available = set(df.columns)
    for name, c in series_cfg.items():
        if c.get("country") in ("US", "CA") and c.get("tenor_years") and c["name"] in available:
            tenors_by_ccy[c["country"]].append((float(c["tenor_years"]), c["name"]))
    for k in tenors_by_ccy: tenors_by_ccy[k].sort(key=lambda x: x[0])

    fig, ax = plt.subplots(figsize=tuple(style["figure_sizes"]["vol_strip"]))
    for country, lst in tenors_by_ccy.items():
        cols = [col for _, col in lst]
        if not cols:
            continue
        vol = compute_rolling_vol_bp(df[["date"] + cols].copy(), cols, window=20)
        vlast = vol.dropna().tail(1)
        if vlast.empty:
            # Not enough history; skip plotting but leave a note
            continue
        latest = vlast.iloc[0]
        xs = [t for t, _ in lst]
        ys = [latest[c] for _, c in lst]
        ax.plot(xs, ys, marker="o" if country == "US" else "s", label=country, color=colors["us" if country == "US" else "ca"], linewidth=1.5)
    ax.set_title("Rolling 20d Realized Vol (bp/day)")
    ax.set_xlabel("Tenor (years)")
    ax.set_ylabel("bp")
    ax.grid(True, alpha=0.2)
    ax.legend()
    return fig


def xccy_spread(df: pd.DataFrame, viz_cfg: dict):
    style = viz_cfg["style"]
    fig, ax = plt.subplots(figsize=tuple(style["figure_sizes"]["xccy_spread"]))
    if "UST10_minus_GoC10_bp" in df.columns:
        ts_all = pd.to_datetime(df["date"]) 
        y_all = df["UST10_minus_GoC10_bp"].astype(float)
        # Restrict to last 1 year for display window, but don't show empty months before first data
        end = ts_all.max()
        min_date = ts_all.min()
        start = max(min_date, end - pd.Timedelta(days=365))
        mask = (ts_all >= start) & (ts_all <= end)
        ts = ts_all[mask]
        y = y_all[mask]
        if len(ts) > 0 and np.isfinite(y).any():
            ax.plot(ts, y, color="#444", linewidth=1.5, marker='o', markersize=2)
        else:
            ax.text(0.5, 0.5, 'No spread data in last 1y', transform=ax.transAxes, ha='center', va='center')
        ax.axhline(0, color="black", linewidth=1)
        # Format dates: monthly ticks, YYYY-MM across full last-year window
        ax.set_xlim(start, end)
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        for label in ax.get_xticklabels():
            label.set_rotation(45)
            label.set_ha('right')
    ax.set_title("UST10 – GoC10 Spread (bp)")
    ax.set_ylabel("bp")
    ax.grid(True, alpha=0.2)
    # Remove legend for cleanliness
    if ax.get_legend() is not None:
        ax.get_legend().remove()

    # Optional FX sparkline below if USD_CAD is present
    if "USD_CAD" in df.columns:
        try:
            from mpl_toolkits.axes_grid1 import make_axes_locatable
            divider = make_axes_locatable(ax)
            # Make FX panel larger and further separated
            ax_fx = divider.append_axes("bottom", size="35%", pad=0.6, sharex=ax)
            ts = pd.to_datetime(df["date"]) 
            y = pd.to_numeric(df["USD_CAD"], errors="coerce")
            # Restrict to the same window as spread
            if len(ts) > 0:
                end = ts.max(); start = max(ts.min(), end - pd.Timedelta(days=365))
                mask = (ts >= start) & (ts <= end)
                ts, y = ts[mask], y[mask]
            ax_fx.plot(ts, y, color="#2ca02c", linewidth=1.2)
            ax_fx.set_ylabel("USD/CAD", fontsize=style["font_size"])
            ax_fx.grid(True, alpha=0.15)
            for label in ax_fx.get_xticklabels():
                label.set_rotation(45)
                label.set_ha('right')
        except Exception:
            pass
    # Add a bit more vertical spacing to avoid overlap
    fig.subplots_adjust(hspace=0.5)
    return fig


def render_and_export_all(df: pd.DataFrame, series_cfg: dict, viz_cfg: dict, countries_cfg: dict):
    out_dir = viz_cfg["export"]["out_dir"]
    save_png = viz_cfg["export"].get("save_png", True)
    save_svg = viz_cfg["export"].get("save_svg", True)

    # Curve snapshot
    fig_curves = curve_snapshot(df, series_cfg, viz_cfg, countries_cfg)
    _save_figure(fig_curves, "curves_snapshot", out_dir, save_png, save_svg)
    plt.close(fig_curves)

    # Slopes
    fig_slopes = slope_trackers(df, viz_cfg)
    _save_figure(fig_slopes, "slopes", out_dir, save_png, save_svg)
    plt.close(fig_slopes)

    # Heatmaps
    hmaps = tenor_change_heatmaps(df, series_cfg, viz_cfg)
    for country, fig in hmaps.items():
        _save_figure(fig, f"heatmap_{country}", out_dir, save_png, save_svg)
        plt.close(fig)

    # Vol strip
    fig_vol = vol_strip(df, series_cfg, viz_cfg)
    _save_figure(fig_vol, "vol_strip", out_dir, save_png, save_svg)
    plt.close(fig_vol)

    # Xccy
    fig_x = xccy_spread(df, viz_cfg)
    _save_figure(fig_x, "xccy_spread", out_dir, save_png, save_svg)
    plt.close(fig_x)


def one_pager(df: pd.DataFrame, series_cfg: dict, viz_cfg: dict, countries_cfg: dict):
    """Compose a one-pager by stitching the already-exported PNGs into a grid.

    This avoids brittle artist copying and guarantees non-empty output.
    """
    style = viz_cfg["style"]
    one_dir = viz_cfg["export"]["one_pager_dir"]
    ensure_dir(one_dir)

    # Ensure individual figures exist (caller usually runs render_and_export_all first)
    out_dir = viz_cfg["export"]["out_dir"]
    today = today_str()
    paths = {
        "curves": os.path.join(out_dir, "curves_snapshot_latest.png"),
        "slopes": os.path.join(out_dir, "slopes_latest.png"),
        "heat_us": os.path.join(out_dir, "heatmap_US_latest.png"),
        "heat_ca": os.path.join(out_dir, "heatmap_CA_latest.png"),
        "vol": os.path.join(out_dir, "vol_strip_latest.png"),
        "xccy": os.path.join(out_dir, "xccy_spread_latest.png"),
    }

    fig = plt.figure(figsize=tuple(style["figure_sizes"]["one_pager"]))
    import matplotlib.gridspec as gridspec
    # Simple 2 columns x 3 rows, equal sizes
    gs = gridspec.GridSpec(3, 2, figure=fig, height_ratios=[1, 1, 1])

    def _ax_image(ax, path, title=None):
        if os.path.exists(path):
            img = plt.imread(path)
            ax.imshow(img, aspect='auto')
            ax.axis('off')
        else:
            ax.text(0.5, 0.5, 'Missing: ' + os.path.basename(path), ha='center', va='center')
            ax.axis('off')
        if title:
            ax.set_title(title, fontsize=style["font_size"])  # small caption

    # Row 1: Curves (left, bigger) and Cross-Country (right, bigger)
    _ax_image(fig.add_subplot(gs[0, 0]), paths["curves"])  # today vs prior
    _ax_image(fig.add_subplot(gs[0, 1]), paths["xccy"])   # US vs CA spread

    # Row 2: Slopes | US Tenor Changes
    _ax_image(fig.add_subplot(gs[1, 0]), paths["slopes"])  # steepness over time
    _ax_image(fig.add_subplot(gs[1, 1]), paths["heat_us"], title="US Tenor Changes")

    # Row 3: Vol | CA Tenor Changes
    _ax_image(fig.add_subplot(gs[2, 0]), paths["vol"])   # vol strip
    _ax_image(fig.add_subplot(gs[2, 1]), paths["heat_ca"], title="CA Tenor Changes")

    fig.suptitle("Treasury vs GoC Dashboard — One Pager", fontsize=style["title_size"])
    fig.tight_layout(rect=[0, 0.03, 1, 0.95])

    base = os.path.join(one_dir, "one_pager_" + today)
    fig.savefig(base + ".png", bbox_inches="tight")
    fig.savefig(os.path.join(one_dir, "one_pager_latest.png"), bbox_inches="tight")
    fig.savefig(base + ".svg", bbox_inches="tight")
    fig.savefig(os.path.join(one_dir, "one_pager_latest.svg"), bbox_inches="tight")
    plt.close(fig)
