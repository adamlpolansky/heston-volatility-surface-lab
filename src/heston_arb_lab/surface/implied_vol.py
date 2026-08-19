"""Market implied-volatility helpers."""

from __future__ import annotations

import pandas as pd

from heston_arb_lab.models.black_scholes import implied_volatility


def add_implied_volatility(
    quotes: pd.DataFrame,
    *,
    spot: float,
    rate: float,
    dividend: float = 0.0,
    price_col: str = "mid",
) -> pd.DataFrame:
    """Compute Black-Scholes implied volatility for every quote row."""

    frame = quotes.copy()
    ivs = []
    for row in frame.itertuples(index=False):
        ivs.append(
            implied_volatility(
                price=float(getattr(row, price_col)),
                spot=spot,
                strike=float(row.strike),
                maturity=float(row.time_to_expiry),
                rate=rate,
                option_type=str(row.right),
                dividend=dividend,
            )
        )
    frame["implied_vol"] = ivs
    frame["total_variance"] = frame["implied_vol"] ** 2 * frame["time_to_expiry"]
    return frame
