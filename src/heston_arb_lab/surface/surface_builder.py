"""Surface construction pipeline and synthetic fixture generation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import pandas as pd

from heston_arb_lab.models.black_scholes import bs_price
from heston_arb_lab.surface.cleaning import clean_option_quotes
from heston_arb_lab.surface.implied_vol import add_implied_volatility


@dataclass(frozen=True)
class SurfaceBuildConfig:
    """Configuration for surface construction."""

    spot: float
    asof: date
    rate: float = 0.04
    dividend: float = 0.0
    max_relative_spread: float = 0.5
    min_mid: float = 0.01


def synthetic_option_chain(
    *,
    symbol: str = "SYNTH",
    spot: float = 100.0,
    asof: date = date(2025, 1, 15),
    rate: float = 0.04,
    dividend: float = 0.0,
) -> pd.DataFrame:
    """Generate a deterministic, clean synthetic option chain."""

    rows: list[dict[str, object]] = []
    expirations = [asof + timedelta(days=30), asof + timedelta(days=60), asof + timedelta(days=90)]
    strikes = [80.0, 90.0, 95.0, 100.0, 105.0, 110.0, 120.0]
    timestamp = datetime(asof.year, asof.month, asof.day, 15, 30)
    for expiration in expirations:
        maturity = max((expiration - asof).days / 365.0, 1.0 / 365.0)
        for strike in strikes:
            smile = 0.18 + 0.08 * abs(math.log(strike / spot)) + 0.02 * maturity
            for right in ("call", "put"):
                mid = bs_price(spot, strike, maturity, rate, smile, right, dividend)
                spread = max(0.02, 0.015 * mid)
                rows.append(
                    {
                        "symbol": symbol,
                        "timestamp": timestamp,
                        "expiration": expiration,
                        "strike": strike,
                        "right": right,
                        "bid": max(mid - spread / 2.0, 0.0),
                        "ask": mid + spread / 2.0,
                        "bid_size": 20,
                        "ask_size": 20,
                        "volume": 100,
                        "open_interest": 500,
                    }
                )
    return pd.DataFrame(rows)


def build_surface(quotes: pd.DataFrame, config: SurfaceBuildConfig) -> pd.DataFrame:
    """Clean quotes and enrich them with IV and surface features."""

    cleaned = clean_option_quotes(
        quotes,
        max_relative_spread=config.max_relative_spread,
        min_mid=config.min_mid,
    )
    frame = cleaned.copy()
    expirations = pd.to_datetime(frame["expiration"]).dt.date
    frame["time_to_expiry"] = [
        max((expiration - config.asof).days / 365.0, 1.0 / 365.0) for expiration in expirations
    ]
    frame = add_implied_volatility(
        frame,
        spot=config.spot,
        rate=config.rate,
        dividend=config.dividend,
    )
    forward = config.spot * ((config.rate - config.dividend) * frame["time_to_expiry"]).map(
        math.exp
    )
    frame["log_moneyness"] = (frame["strike"] / forward).map(math.log)
    return frame.loc[frame["implied_vol"].notna()].reset_index(drop=True)
