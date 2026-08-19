"""Execution cost assumptions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostConfig:
    """Backtest cost configuration."""

    option_fee_per_contract: float = 0.65
    underlying_fee_per_share: float = 0.0
    slippage_bps: float = 1.0
    option_multiplier: float = 100.0


def slippage_cost(price: float, quantity: float, multiplier: float, slippage_bps: float) -> float:
    """Return absolute slippage cost."""

    return abs(price * quantity * multiplier) * slippage_bps / 10_000.0
