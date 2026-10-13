"""Day-ahead arbitrage value of a grid-scale battery in the Netherlands.

For each day we solve a small linear programme: given the 24 hourly
day-ahead prices, when should a battery charge and discharge to earn
the most money?

Day-ahead prices are published the day before delivery, so optimising
against them with full knowledge of the day is a realistic assumption
for a battery that only trades on the day-ahead market.

Battery assumptions (simple, stated on purpose):
- power: 1 MW, so results read as EUR per MW
- round-trip efficiency: 88% (split evenly between charge and discharge)
- at most one full cycle per day (a common warranty limit)
- the battery starts and ends each day empty
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp


@dataclass
class Battery:
    power_mw: float = 1.0
    duration_h: float = 2.0
    round_trip_eff: float = 0.88
    max_cycles_per_day: float = 1.0

    @property
    def energy_mwh(self) -> float:
        return self.power_mw * self.duration_h


def optimise_day(prices: np.ndarray, bat: Battery) -> dict:
    """Return the best charge/discharge schedule for one day.

    Decision variables, for each hour t:
      c[t]  energy bought from the grid (MWh)
      d[t]  energy sold to the grid (MWh)
      s[t]  state of charge at the end of hour t (MWh)
      u[t]  1 if the battery is charging in hour t, 0 if discharging

    Why u[t]? Without it, a pure linear model "cheats" on negative-price
    hours: it charges and discharges at the same time, wasting energy
    through efficiency losses just to get paid for consuming power.
    A real battery can't do that, so u[t] forces one mode per hour.
    This makes it a mixed-integer linear programme (MILP).
    """
    n = len(prices)
    eta = np.sqrt(bat.round_trip_eff)  # one-way efficiency
    p_max = bat.power_mw

    # Variable order: [c (n), d (n), s (n), u (n)]
    # milp minimises, so minimise cost = price*charge - price*discharge
    cost = np.concatenate([prices, -prices, np.zeros(n), np.zeros(n)])

    rows, lo, hi = [], [], []

    # State of charge: s[t] - s[t-1] - eta*c[t] + d[t]/eta = 0
    for t in range(n):
        r = np.zeros(4 * n)
        r[t] = -eta
        r[n + t] = 1 / eta
        r[2 * n + t] = 1
        if t > 0:
            r[2 * n + t - 1] = -1
        rows.append(r); lo.append(0); hi.append(0)

    # One mode per hour: c[t] <= P*u[t] and d[t] <= P*(1 - u[t])
    for t in range(n):
        r = np.zeros(4 * n); r[t] = 1; r[3 * n + t] = -p_max
        rows.append(r); lo.append(-np.inf); hi.append(0)
        r = np.zeros(4 * n); r[n + t] = 1; r[3 * n + t] = p_max
        rows.append(r); lo.append(-np.inf); hi.append(p_max)

    # Cycle limit: total energy sold <= cycles * capacity
    r = np.zeros(4 * n); r[n:2 * n] = 1
    rows.append(r); lo.append(-np.inf); hi.append(bat.max_cycles_per_day * bat.energy_mwh)

    lower = np.zeros(4 * n)
    upper = np.concatenate([
        np.full(n, p_max),                                 # charge
        np.full(n, p_max),                                 # discharge
        np.append(np.full(n - 1, bat.energy_mwh), 0.0),    # SoC, end the day empty
        np.ones(n),                                        # mode
    ])
    integrality = np.concatenate([np.zeros(3 * n), np.ones(n)])

    res = milp(cost,
               constraints=LinearConstraint(np.array(rows), lo, hi),
               bounds=Bounds(lower, upper),
               integrality=integrality)
    if not res.success:
        raise RuntimeError(res.message)

    charge, discharge = res.x[:n], res.x[n:2 * n]
    return {
        "revenue": float(prices @ (discharge - charge)),
        "energy_sold_mwh": float(discharge.sum()),
        "charge": charge,
        "discharge": discharge,
    }


def rule_based_day(prices: pd.Series, bat: Battery) -> float:
    """A simple benchmark: charge in the cheapest midday hours (solar),
    discharge in the most expensive evening hours. No optimisation."""
    hours = int(bat.duration_h)
    eta = np.sqrt(bat.round_trip_eff)
    midday = prices[(prices.index.hour >= 10) & (prices.index.hour < 16)]
    evening = prices[(prices.index.hour >= 17) & (prices.index.hour < 22)]
    if len(midday) < hours or len(evening) < hours:
        return 0.0
    buy = midday.nsmallest(hours).sum() * bat.power_mw
    sell = evening.nlargest(hours).sum() * bat.power_mw * eta * eta
    return float(sell - buy)


def run(prices: pd.DataFrame, bat: Battery) -> pd.DataFrame:
    """Optimise every day and return one row per day."""
    s = prices.set_index("ts")["price_eur_mwh"]
    rows = []
    for day, p in s.groupby(s.index.date):
        if len(p) < 23:  # skip incomplete days
            continue
        opt = optimise_day(p.to_numpy(), bat)
        rows.append({
            "day": pd.Timestamp(day),
            "optimal_revenue": opt["revenue"],
            "rule_revenue": rule_based_day(p, bat),
            "energy_sold_mwh": opt["energy_sold_mwh"],
        })
    return pd.DataFrame(rows)
