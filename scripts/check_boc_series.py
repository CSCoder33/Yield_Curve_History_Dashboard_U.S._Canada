import sys
import requests
import pandas as pd


def check_series(series_id: str, start_date: str = "2018-01-01"):
    base = f"https://www.bankofcanada.ca/valet/observations/{series_id}"
    headers = {"Accept": "application/json"}
    for params in ({"start_date": start_date}, {"recent": 10}):
        try:
            r = requests.get(base, params=params, headers=headers, timeout=15)
            print(f"Series {series_id} GET {r.url} -> {r.status_code}")
            r.raise_for_status()
            data = r.json().get("observations", [])
            if not data:
                print("  No observations returned.")
                continue
            rows = [
                {
                    "date": d.get("d"),
                    "value": list({k: v for k, v in d.items() if k != "d"}.values())[0].get("v"),
                }
                for d in data[-5:]
            ]
            df = pd.DataFrame(rows)
            print(df)
            return True
        except Exception as e:
            print("  Error:", e)
    return False


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/check_boc_series.py <SERIES_ID> [SERIES_ID ...]")
        sys.exit(1)
    for sid in sys.argv[1:]:
        ok = check_series(sid)
        print("Result:", sid, "OK" if ok else "FAILED")


if __name__ == "__main__":
    main()

