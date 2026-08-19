"""Calendar total-variance signal scanner."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from heston_arb_lab.surface.no_arbitrage import check_calendar_total_variance


def scan_calendar_violations(surface: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert calendar variance violations into signal candidates."""

    violations = check_calendar_total_variance(surface)
    return [
        {
            "signal_id": f"calendar-{row.symbol}-{row.right}-{row.strike}",
            "symbol": row.symbol,
            "asof": datetime.utcnow(),
            "signal_type": "calendar_total_variance",
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
