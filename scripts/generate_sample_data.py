import os
from datetime import date, timedelta
import random

import pandas as pd

OUT_DIR = "data/raw/sample"
os.makedirs(OUT_DIR, exist_ok=True)


def gen_series(name: str, base: float, drift: float, vol: float, days: int = 260):
    # simple GBM-ish random walk in levels (%), non-negative
    today = date.today()
    dates = pd.bdate_range(end=today, periods=days).date
    x = base
    vals = []
    for _ in dates:
        x = max(-0.5, x + drift + random.gauss(0, vol))
        vals.append(round(x, 3))
    df = pd.DataFrame({"date": dates, "value": vals})
    df.to_csv(os.path.join(OUT_DIR, f"sample_{name}_{today.strftime('%Y-%m-%d')}.csv"), index=False)


def main():
    # US curve roughly upward sloping
    gen_series("US_3M", 5.3, -0.001, 0.03)
    gen_series("US_2Y", 4.6, -0.001, 0.03)
    gen_series("US_5Y", 4.2, -0.001, 0.03)
    gen_series("US_10Y", 4.1, 0.0, 0.03)
    gen_series("US_30Y", 4.2, 0.0005, 0.03)

    # CA curve a touch lower
    gen_series("CA_3M", 5.1, -0.001, 0.03)
    gen_series("CA_2Y", 4.2, -0.001, 0.03)
    gen_series("CA_5Y", 3.7, -0.001, 0.03)
    gen_series("CA_10Y", 3.6, 0.0, 0.03)
    gen_series("CA_30Y", 3.7, 0.0005, 0.03)

    print("Sample data created in", OUT_DIR)


if __name__ == "__main__":
    main()

