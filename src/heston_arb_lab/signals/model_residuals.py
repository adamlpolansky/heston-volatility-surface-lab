"""Heston model-relative residual signals."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from heston_arb_lab.models.heston_cf import HestonParams
from heston_arb_lab.models.heston_pricer import heston_implied_volatility, heston_price
from heston_arb_lab.signals.ranking import score_signal


def scan_heston_residuals(
    surface: pd.DataFrame,
    *,
    spot: float,
    rate: float,
    params: HestonParams,
    dividend: float = 0.0,
    min_zscore: float = 1.0,
) -> list[dict[str, Any]]:
    """Scan market-vs-Heston IV residuals."""

    residuals = []
    for row in surface.itertuples(index=False):
        model_price = heston_price(
            spot,
            float(row.strike),
            float(row.time_to_expiry),
            rate,
            params,
            str(row.right),
            dividend,
        )
        model_iv = heston_implied_volatility(
            spot,
            float(row.strike),
            float(row.time_to_expiry),
            rate,
            params,
            str(row.right),
            dividend,
        )
        market_iv = float(row.implied_vol)
        iv_scale = max(float(getattr(row, "relative_spread", 0.05)), 0.01)
        zscore = (market_iv - model_iv) / iv_scale
        if abs(zscore) < min_zscore:
            continue
        side = "buy" if zscore < 0 else "sell"
        residuals.append(
            score_signal(
                {
                    "signal_id": (
                        f"heston-residual-{row.symbol}-{row.expiration}-{row.strike}-{row.right}"
                    ),
                    "symbol": row.symbol,
                    "asof": pd.to_datetime(
                        getattr(row, "timestamp", datetime.utcnow())
                    ).to_pydatetime(),
                    "signal_type": "heston_residual",
                    "direction": side,
                    "legs": [
                        {
                            "symbol": row.symbol,
                            "expiration": str(row.expiration),
                            "strike": float(row.strike),
                            "right": row.right,
                            "side": side,
                            "quantity": 1,
                            "bid": float(row.bid),
                            "ask": float(row.ask),
                            "mid": float(row.mid),
                            "multiplier": 100,
                            "relative_spread": float(getattr(row, "relative_spread", 0.0)),
                        }
                    ],
                    "market_iv": market_iv,
                    "model_iv": model_iv,
                    "market_price": float(row.mid),
                    "model_price": model_price,
                    "zscore": zscore,
                    "gross_edge": abs(float(row.mid) - model_price) * 100.0,
                    "estimated_cost": 0.0,
                    "net_edge": 0.0,
                    "confidence": 0.0,
                    "rejection_flags": [],
                }
            )
        )
    return residuals
