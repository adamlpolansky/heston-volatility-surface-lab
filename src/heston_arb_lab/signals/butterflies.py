"""Butterfly convexity signal scanner."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from heston_arb_lab.surface.no_arbitrage import check_butterfly_convexity


def scan_butterfly_violations(surface: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert butterfly convexity violations into signal candidates."""

    violations = check_butterfly_convexity(surface)
    return [
        {
            "signal_id": f"butterfly-{row.symbol}-{row.expiration}-{row.center_strike}",
            "symbol": row.symbol,
            "asof": datetime.utcnow(),
            "signal_type": "butterfly_convexity",
            "legs": [],
            "gross_edge": float(row.severity) * 100.0,
            "estimated_cost": 0.0,
            "net_edge": float(row.severity) * 100.0,
            "confidence": 0.5,
            "rejection_flags": [],
            "message": row.message,
        }
        for row in violations.itertuples(index=False)
    ]
