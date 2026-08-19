"""Delta hedging helpers."""

from __future__ import annotations


def underlying_hedge_quantity(
    option_delta: float, option_quantity: float, multiplier: float = 100.0
) -> float:
    """Return underlying shares required for a delta-neutral hedge."""

    return -option_delta * option_quantity * multiplier
