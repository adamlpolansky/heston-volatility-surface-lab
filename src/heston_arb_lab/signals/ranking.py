"""Signal scoring and ranking."""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any

import pandas as pd

from heston_arb_lab.backtest.execution import validate_trade_side


def estimate_leg_cost(leg: dict[str, Any], fee_per_contract: float = 0.65) -> float:
    """Estimate conservative transaction cost for a signal leg."""

    validate_trade_side(leg.get("side"))
    bid = float(leg.get("bid", leg.get("mid", 0.0)))
    ask = float(leg.get("ask", leg.get("mid", bid)))
    quantity = abs(float(leg.get("quantity", 1.0)))
    multiplier = float(leg.get("multiplier", 100.0))
    spread_cost = max(ask - bid, 0.0) * multiplier * quantity * 0.5
    return spread_cost + fee_per_contract * quantity


def score_signal(
    signal: dict[str, Any],
    *,
    fee_per_contract: float = 0.65,
    cost_buffer: float = 0.0,
) -> dict[str, Any]:
    """Attach cost, net edge, confidence, and rejection flags."""

    enriched = signal.copy()
    raw_legs = enriched.get("legs")
    if raw_legs is None:
        raise ValueError("signal must include at least one execution leg")
    legs = list(raw_legs)
    if not legs:
        raise ValueError("signal must include at least one execution leg")
    for leg in legs:
        validate_trade_side(leg.get("side"))
    estimated_cost = float(enriched.get("estimated_cost", 0.0)) or sum(
        estimate_leg_cost(leg, fee_per_contract) for leg in legs
    )
    gross_edge = float(enriched.get("gross_edge", 0.0))
    net_edge = gross_edge - estimated_cost - cost_buffer
    rejection_flags = list(enriched.get("rejection_flags", []))
    if net_edge <= 0:
        rejection_flags.append("edge_below_cost_buffer")
    if any(float(leg.get("relative_spread", 0.0)) > 0.5 for leg in legs):
        rejection_flags.append("wide_spread")
    confidence = 1.0 / (1.0 + math.exp(-net_edge / max(abs(gross_edge), 1.0)))
    enriched.update(
        {
            "estimated_cost": estimated_cost,
            "net_edge": net_edge,
            "confidence": confidence,
            "rejection_flags": sorted(set(rejection_flags)),
        }
    )
    return enriched


def rank_signals(
    signals: Iterable[dict[str, Any]],
    *,
    min_net_edge: float = 0.0,
    fee_per_contract: float = 0.65,
    cost_buffer: float = 0.0,
) -> pd.DataFrame:
    """Return ranked signals by net edge and confidence."""

    scored = [
        score_signal(signal, fee_per_contract=fee_per_contract, cost_buffer=cost_buffer)
        for signal in signals
    ]
    if not scored:
        return pd.DataFrame()
    frame = pd.DataFrame(scored)
    frame = frame.loc[frame["net_edge"] >= min_net_edge].copy()
    if frame.empty:
        return frame
    return frame.sort_values(["net_edge", "confidence"], ascending=False).reset_index(drop=True)
