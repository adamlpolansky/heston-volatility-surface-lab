"""Put-call parity signal scanner."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

import pandas as pd

from heston_arb_lab.models.black_scholes import put_call_parity_residual
from heston_arb_lab.signals.ranking import score_signal


def scan_put_call_parity(
    surface: pd.DataFrame,
    *,
    spot: float,
    rate: float,
    dividend: float = 0.0,
    min_abs_residual: float = 0.01,
) -> list[dict[str, Any]]:
    """Scan matched call/put quotes for parity residuals."""

    signals: list[dict[str, Any]] = []
    for keys, group in surface.groupby(["symbol", "expiration", "strike"]):
        symbol, expiration, strike = keys
        pivot = group.set_index("right")
        if not {"call", "put"}.issubset(set(pivot.index)):
            continue
        call = pivot.loc["call"]
        put = pivot.loc["put"]
        maturity = float(call.get("time_to_expiry", 0.0))
        residual = put_call_parity_residual(
            float(call["mid"]),
            float(put["mid"]),
            spot,
            float(strike),
            maturity,
            rate,
            dividend,
        )
        if abs(residual) < min_abs_residual:
            continue
        asof = pd.to_datetime(call.get("timestamp", datetime.now(UTC))).to_pydatetime()
        direction = "sell_call_buy_put" if residual > 0 else "buy_call_sell_put"
        legs = [
            {
                "symbol": symbol,
                "expiration": str(expiration),
                "strike": float(strike),
                "right": "call",
                "side": "sell" if residual > 0 else "buy",
                "quantity": 1,
                "bid": float(call["bid"]),
                "ask": float(call["ask"]),
                "mid": float(call["mid"]),
                "multiplier": 100,
                "relative_spread": float(call.get("relative_spread", 0.0)),
            },
            {
                "symbol": symbol,
                "expiration": str(expiration),
                "strike": float(strike),
                "right": "put",
                "side": "buy" if residual > 0 else "sell",
                "quantity": 1,
                "bid": float(put["bid"]),
                "ask": float(put["ask"]),
                "mid": float(put["mid"]),
                "multiplier": 100,
                "relative_spread": float(put.get("relative_spread", 0.0)),
            },
        ]
        signal = {
            "signal_id": f"parity-{symbol}-{expiration}-{float(strike):.2f}",
            "symbol": symbol,
            "asof": asof,
            "signal_type": "put_call_parity",
            "direction": direction,
            "legs": legs,
            "theoretical_value": spot * math.exp(-dividend * maturity)
            - float(strike) * math.exp(-rate * maturity),
            "gross_edge": abs(residual) * 100.0,
            "estimated_cost": 0.0,
            "net_edge": 0.0,
            "confidence": 0.0,
            "rejection_flags": [],
        }
        signals.append(score_signal(signal))
    return signals
