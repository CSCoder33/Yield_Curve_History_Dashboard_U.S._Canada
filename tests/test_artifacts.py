import os
import pandas as pd

from src.utils import read_yaml
from src.viz import render_and_export_all, one_pager


def test_generate_artifacts(tmp_path):
    df = pd.read_csv("data/processed/daily.csv")
    series_cfg = read_yaml("config/series.yaml")
    viz_cfg = read_yaml("config/viz.yaml")
    countries_cfg = read_yaml("config/countries.yaml")
    # Override output dirs to temporary path
    viz_cfg["export"]["out_dir"] = str(tmp_path)
    viz_cfg["export"]["one_pager_dir"] = str(tmp_path)
    render_and_export_all(df, series_cfg, viz_cfg, countries_cfg)
    one_pager(df, series_cfg, viz_cfg, countries_cfg)
    # Check at least a couple of files exist
    files = list(os.listdir(tmp_path))
    assert any(f.startswith("curves_snapshot_") for f in files)
    assert any(f.startswith("one_pager_") for f in files)

