import os
import pandas as pd


def test_slopes_correctness():
    path = "data/processed/daily.csv"
    assert os.path.exists(path), "Processed CSV missing"
    df = pd.read_csv(path)
    # Check last row
    r = df.iloc[-1]
    assert abs((r["US_10Y"] - r["US_2Y"]) - r["US_2s10s"]) < 1e-6
    assert abs((r["US_30Y"] - r["US_5Y"]) - r["US_5s30s"]) < 1e-6
    assert abs((r["CA_10Y"] - r["CA_2Y"]) - r["CA_2s10s"]) < 1e-6
    assert abs((r["CA_30Y"] - r["CA_5Y"]) - r["CA_5s30s"]) < 1e-6


def test_spread_bp():
    df = pd.read_csv("data/processed/daily.csv")
    r = df.iloc[-1]
    assert abs(((r["US_10Y"] - r["CA_10Y"]) * 100) - r["UST10_minus_GoC10_bp"]) < 1e-6

