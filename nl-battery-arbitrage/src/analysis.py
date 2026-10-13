"""Run the full analysis: SQL market statistics + battery arbitrage model.

Usage (from the project folder):
    python src/fetch_prices.py   # download data (only needed once)
    python src/analysis.py       # run SQL queries, battery model, charts
"""
from pathlib import Path

import duckdb
import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from battery import Battery, run  # noqa: E402

OUT = Path("outputs")
SQL = Path("sql")


def sql(con: duckdb.DuckDBPyConnection, name: str) -> pd.DataFrame | None:
    query = (SQL / name).read_text()
    result = con.execute(query)
    return result.df() if result.description else None


def main() -> None:
    OUT.mkdir(exist_ok=True)
    prices = pd.read_csv("data/nl_day_ahead_hourly.csv", parse_dates=["ts"])
    prices["ts"] = pd.to_datetime(prices["ts"], utc=True).dt.tz_convert("Europe/Amsterdam")

    # ---------- 1. Market statistics in SQL (DuckDB) ----------
    con = duckdb.connect()
    con.register("prices_df", prices.assign(ts=prices["ts"].dt.tz_localize(None)))
    con.execute("CREATE TABLE prices AS SELECT * FROM prices_df")
    sql(con, "01_daily_spreads.sql")
    yearly = sql(con, "02_yearly_summary.sql")
    hours = sql(con, "03_hour_profile.sql")
    rolling = sql(con, "04_rolling_spread.sql")
    yearly.to_csv(OUT / "yearly_market_summary.csv", index=False)
    print("\nYearly market summary\n", yearly.to_string(index=False))

    # ---------- 2. Battery model: 1h, 2h and 4h batteries ----------
    results = []
    for duration in (1, 2, 4):
        bat = Battery(duration_h=duration)
        daily = run(prices, bat)
        daily["year"] = daily["day"].dt.year
        daily["duration_h"] = duration
        results.append(daily)
    daily_all = pd.concat(results)

    summary = (
        daily_all.groupby(["duration_h", "year"])
        .agg(days=("day", "count"),
             optimal_eur=("optimal_revenue", "sum"),
             rule_eur=("rule_revenue", "sum"),
             mwh_sold=("energy_sold_mwh", "sum"))
        .reset_index()
    )
    # Annualise so partial years (2026) compare fairly with full ones
    summary["optimal_eur_per_mw_year"] = (summary["optimal_eur"] / summary["days"] * 365).round(0)
    summary["rule_eur_per_mw_year"] = (summary["rule_eur"] / summary["days"] * 365).round(0)
    summary["rule_captures_pct"] = (100 * summary["rule_eur"] / summary["optimal_eur"]).round(0)
    summary = summary.drop(columns=["optimal_eur", "rule_eur"])
    summary.to_csv(OUT / "battery_revenue_summary.csv", index=False)
    print("\nBattery arbitrage revenue (day-ahead only, EUR per MW per year)\n",
          summary.to_string(index=False))

    # ---------- 3. Charts ----------
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(hours["hour"], hours["summer_avg"], marker="o", label="Apr–Sep")
    ax.plot(hours["hour"], hours["winter_avg"], marker="o", label="Oct–Mar")
    ax.set(title="Average Dutch day-ahead price by hour of day",
           xlabel="Hour of day", ylabel="EUR/MWh")
    ax.axhline(0, color="grey", lw=0.8)
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "price_by_hour.png", dpi=150)

    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(rolling["day"], rolling["spread"], color="lightgrey", lw=0.6, label="Daily spread")
    ax.plot(rolling["day"], rolling["spread_30d_avg"], color="tab:blue", lw=2, label="30-day average")
    ax.set(title="Daily max–min price spread, Netherlands day-ahead",
           ylabel="EUR/MWh")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "daily_spread.png", dpi=150)

    pivot = summary.pivot(index="year", columns="duration_h", values="optimal_eur_per_mw_year")
    ax = pivot.plot(kind="bar", figsize=(9, 4), rot=0)
    ax.set(title="Optimal day-ahead arbitrage revenue by battery duration",
           xlabel="Year (2026 annualised)", ylabel="EUR per MW per year")
    ax.legend([f"{d}h battery" for d in pivot.columns])
    ax.grid(alpha=0.3, axis="y")
    plt.tight_layout()
    plt.savefig(OUT / "revenue_by_duration.png", dpi=150)
    print("\nCharts saved to outputs/")


if __name__ == "__main__":
    main()
