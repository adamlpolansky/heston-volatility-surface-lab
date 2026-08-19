"""Forward estimation helpers."""

from __future__ import annotations

import math

import pandas as pd


def estimate_forward_from_parity(
    quotes: pd.DataFrame,
    *,
    spot: float,
    rate: float,
    dividend: float = 0.0,
    maturity_col: str = "time_to_expiry",
) -> pd.DataFrame:
    """Estimate forward per expiry from put-call parity when matched quotes exist."""

    records: list[dict[str, float | str]] = []
    for expiration, group in quotes.groupby("expiration"):
        pivot = group.pivot_table(index="strike", columns="right", values="mid", aggfunc="mean")
        maturity = float(group[maturity_col].iloc[0]) if maturity_col in group.columns else 0.0
        parity_forwards = []
        if {"call", "put"}.issubset(pivot.columns):
            for strike, row in pivot.dropna(subset=["call", "put"]).iterrows():
                forward = float(strike) + math.exp(rate * maturity) * float(
                    row["call"] - row["put"]
                )
                parity_forwards.append(forward)
        fallback = spot * math.exp((rate - dividend) * maturity)
        records.append(
            {
                "expiration": expiration,
                "time_to_expiry": maturity,
                "forward": float(pd.Series(parity_forwards).median())
                if parity_forwards
                else fallback,
                "source": "put_call_parity" if parity_forwards else "spot_carry",
            }
        )
    return pd.DataFrame(records)
