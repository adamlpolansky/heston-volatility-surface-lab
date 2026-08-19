"""Vertical-spread signal scanner."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from heston_arb_lab.surface.no_arbitrage import check_vertical_bounds


def scan_vertical_violations(surface: pd.DataFrame, *, rate: float = 0.0) -> list[dict[str, Any]]:
    """Convert vertical bound violations into signal candidates."""

    violations = check_vertical_bounds(surface, rate=rate)
    signals: list[dict[str, Any]] = []
    for row in violations.itertuples(index=False):
        signals.append(
            {
                "signal_id": (
                    f"vertical-{row.symbol}-{row.expiration}-{row.lower_strike}-{row.upper_strike}"
                ),
                "symbol": row.symbol,
                "asof": datetime.utcnow(),
                "signal_type": "vertical_violation",
                "legs": [],
                "gross_edge": float(row.severity) * 100.0,
                "estimated_cost": 0.0,
                "net_edge": float(row.severity) * 100.0,
                "confidence": 0.5,
                "rejection_flags": [],
                "message": row.message,
            }
        )
    return signals
