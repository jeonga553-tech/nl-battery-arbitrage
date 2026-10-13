"""Download Dutch day-ahead electricity prices from the Energy-Charts API.

Source: Energy-Charts (Fraunhofer ISE), data licensed CC BY 4.0.
Prices are in EUR/MWh. Since October 2025 the day-ahead market uses
15-minute periods, so everything is averaged to hourly values to keep
the full history on one consistent basis.

Each month is cached in data/raw/, so re-running only downloads
what is missing. The free API is rate-limited, so we retry with a wait.
"""
from datetime import date
from pathlib import Path
import time

import pandas as pd
import requests

API = "https://api.energy-charts.info/price"
RAW = Path("data/raw")


def fetch_month(year: int, month: int) -> pd.DataFrame:
    cache = RAW / f"{year}-{month:02d}.csv"
    if cache.exists():
        return pd.read_csv(cache)

    start = date(year, month, 1)
    end = date(year + (month == 12), month % 12 + 1, 1)
    for attempt in range(6):
        resp = requests.get(
            API,
            params={"bzn": "NL", "start": start.isoformat(), "end": end.isoformat()},
            timeout=60,
        )
        if resp.status_code == 429:  # too many requests: wait and try again
            wait = 20 * (attempt + 1)
            print(f"  rate limited, waiting {wait}s")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        js = resp.json()
        df = pd.DataFrame({"unix": js["unix_seconds"], "price": js["price"]})
        df.to_csv(cache, index=False)
        time.sleep(3)
        return df
    raise RuntimeError(f"could not download {year}-{month:02d}")


def main(first_year: int = 2023, last: date = date(2026, 9, 30)) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    frames = []
    for year in range(first_year, last.year + 1):
        for month in range(1, 13):
            if date(year, month, 1) > last:
                break
            frames.append(fetch_month(year, month))
            print(f"have {year}-{month:02d}")

    raw = pd.concat(frames).drop_duplicates("unix").dropna()
    raw["ts"] = pd.to_datetime(raw["unix"], unit="s", utc=True).dt.tz_convert("Europe/Amsterdam")
    hourly = raw.set_index("ts")["price"].resample("1h").mean().dropna().reset_index()
    hourly = hourly[hourly["ts"].dt.date <= last]
    hourly.columns = ["ts", "price_eur_mwh"]
    hourly.to_csv("data/nl_day_ahead_hourly.csv", index=False)
    print(f"saved {len(hourly):,} hourly prices, {hourly.ts.min()} to {hourly.ts.max()}")


if __name__ == "__main__":
    main()
