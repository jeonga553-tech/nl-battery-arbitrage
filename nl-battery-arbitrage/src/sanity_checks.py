"""Sanity checks for the battery model.

1. Toy day with known answer: 12 hours at 10 EUR, 12 hours at 100 EUR.
   A 1 MW / 2 MWh battery with 88% round-trip efficiency stores 2 MWh,
   buys 2/sqrt(0.88) MWh at 10 and sells 2*sqrt(0.88) MWh at 100.
2. Simultaneous charging and discharging: a linear model can "cheat" on
   negative-price hours by charging and discharging at the same time to
   burn energy. Count how often that happens on the real data.
"""
import numpy as np
import pandas as pd

from battery import Battery, optimise_day


def main() -> None:
    bat = Battery(duration_h=2)
    eta = np.sqrt(bat.round_trip_eff)

    toy = np.array([10.0] * 12 + [100.0] * 12)
    expected = 2 * eta * 100 - 2 / eta * 10
    got = optimise_day(toy, bat)["revenue"]
    print(f"toy day: model {got:.2f}, hand calculation {expected:.2f}")
    assert abs(got - expected) < 1e-6

    prices = pd.read_csv("data/nl_day_ahead_hourly.csv")
    prices["ts"] = pd.to_datetime(prices["ts"], utc=True).dt.tz_convert("Europe/Amsterdam")
    s = prices.set_index("ts")["price_eur_mwh"]
    days = overlap_days = 0
    for _, p in s.groupby(s.index.date):
        if len(p) < 23:
            continue
        r = optimise_day(p.to_numpy(), bat)
        days += 1
        if np.minimum(r["charge"], r["discharge"]).sum() > 1e-6:
            overlap_days += 1
    print(f"days checked: {days}, days with simultaneous charge+discharge: {overlap_days}")


if __name__ == "__main__":
    main()
