"""Model Greek helpers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Greeks:
    """Finite-difference Greek bundle."""

    delta: float
    gamma: float
    vega: float


def finite_difference_greeks(
    price_fn: Callable[[float, float], float],
    *,
    spot: float,
    volatility: float,
    spot_step: float = 0.01,
    vol_step: float = 0.0001,
) -> Greeks:
    """Estimate delta, gamma, and vega for `price_fn(spot, volatility)`."""

    up = price_fn(spot + spot_step, volatility)
    mid = price_fn(spot, volatility)
    down = price_fn(spot - spot_step, volatility)
    vol_up = price_fn(spot, volatility + vol_step)
    delta = (up - down) / (2.0 * spot_step)
    gamma = (up - 2.0 * mid + down) / (spot_step * spot_step)
    vega = (vol_up - mid) / vol_step
    return Greeks(delta=delta, gamma=gamma, vega=vega)
