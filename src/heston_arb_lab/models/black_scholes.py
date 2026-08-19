"""Black-Scholes pricing, Greeks, parity, and implied volatility."""

from __future__ import annotations

import math
from typing import Literal

from heston_arb_lab.utils.math import normal_cdf, normal_pdf

OptionType = Literal["call", "put"]

_MIN_VOL = 1e-8
_MIN_T = 1e-12


def _right(option_type: str) -> OptionType:
    lowered = option_type.lower()
    if lowered in {"c", "call"}:
        return "call"
    if lowered in {"p", "put"}:
        return "put"
    raise ValueError("option_type must be 'call' or 'put'")


def _discounted_intrinsic(
    spot: float,
    strike: float,
    maturity: float,
    rate: float,
    dividend: float,
    option_type: OptionType,
) -> float:
    forward_spot = spot * math.exp(-dividend * maturity)
    discounted_strike = strike * math.exp(-rate * maturity)
    if option_type == "call":
        return max(forward_spot - discounted_strike, 0.0)
    return max(discounted_strike - forward_spot, 0.0)


def _d1_d2(
    spot: float,
    strike: float,
    maturity: float,
    rate: float,
    volatility: float,
    dividend: float,
) -> tuple[float, float]:
    vol_sqrt_t = volatility * math.sqrt(max(maturity, _MIN_T))
    d1 = (
        math.log(max(spot, 1e-300) / max(strike, 1e-300))
        + (rate - dividend + 0.5 * volatility * volatility) * maturity
    ) / vol_sqrt_t
    return d1, d1 - vol_sqrt_t


def bs_price(
    spot: float,
    strike: float,
    maturity: float,
    rate: float,
    volatility: float,
    option_type: str,
    dividend: float = 0.0,
) -> float:
    """Return the European Black-Scholes option price."""

    right = _right(option_type)
    if maturity <= 0.0:
        return max(spot - strike, 0.0) if right == "call" else max(strike - spot, 0.0)
    if volatility <= _MIN_VOL or spot <= 0.0 or strike <= 0.0:
        return _discounted_intrinsic(spot, strike, maturity, rate, dividend, right)

    d1, d2 = _d1_d2(spot, strike, maturity, rate, volatility, dividend)
    discounted_spot = spot * math.exp(-dividend * maturity)
    discounted_strike = strike * math.exp(-rate * maturity)
    if right == "call":
        return discounted_spot * normal_cdf(d1) - discounted_strike * normal_cdf(d2)
    return discounted_strike * normal_cdf(-d2) - discounted_spot * normal_cdf(-d1)


def bs_delta(
    spot: float,
    strike: float,
    maturity: float,
    rate: float,
    volatility: float,
    option_type: str,
    dividend: float = 0.0,
) -> float:
    """Return Black-Scholes delta."""

    right = _right(option_type)
    if maturity <= 0.0 or volatility <= _MIN_VOL:
        if right == "call":
            return 1.0 if spot > strike else 0.0
        return -1.0 if spot < strike else 0.0
    d1, _ = _d1_d2(spot, strike, maturity, rate, volatility, dividend)
    discounted = math.exp(-dividend * maturity)
    return discounted * normal_cdf(d1) if right == "call" else discounted * (normal_cdf(d1) - 1.0)


def bs_gamma(
    spot: float,
    strike: float,
    maturity: float,
    rate: float,
    volatility: float,
    dividend: float = 0.0,
) -> float:
    """Return Black-Scholes gamma."""

    if maturity <= 0.0 or volatility <= _MIN_VOL or spot <= 0.0:
        return 0.0
    d1, _ = _d1_d2(spot, strike, maturity, rate, volatility, dividend)
    return (
        math.exp(-dividend * maturity) * normal_pdf(d1) / (spot * volatility * math.sqrt(maturity))
    )


def bs_vega(
    spot: float,
    strike: float,
    maturity: float,
    rate: float,
    volatility: float,
    dividend: float = 0.0,
) -> float:
    """Return Black-Scholes vega per 1.00 volatility point."""

    if maturity <= 0.0 or volatility <= _MIN_VOL:
        return 0.0
    d1, _ = _d1_d2(spot, strike, maturity, rate, volatility, dividend)
    return spot * math.exp(-dividend * maturity) * normal_pdf(d1) * math.sqrt(maturity)


def bs_theta(
    spot: float,
    strike: float,
    maturity: float,
    rate: float,
    volatility: float,
    option_type: str,
    dividend: float = 0.0,
) -> float:
    """Return annualized Black-Scholes theta."""

    right = _right(option_type)
    if maturity <= 0.0 or volatility <= _MIN_VOL:
        return 0.0
    d1, d2 = _d1_d2(spot, strike, maturity, rate, volatility, dividend)
    first = -(
        spot
        * math.exp(-dividend * maturity)
        * normal_pdf(d1)
        * volatility
        / (2.0 * math.sqrt(maturity))
    )
    if right == "call":
        return (
            first
            - rate * strike * math.exp(-rate * maturity) * normal_cdf(d2)
            + dividend * spot * math.exp(-dividend * maturity) * normal_cdf(d1)
        )
    return (
        first
        + rate * strike * math.exp(-rate * maturity) * normal_cdf(-d2)
        - dividend * spot * math.exp(-dividend * maturity) * normal_cdf(-d1)
    )


def bs_rho(
    spot: float,
    strike: float,
    maturity: float,
    rate: float,
    volatility: float,
    option_type: str,
    dividend: float = 0.0,
) -> float:
    """Return Black-Scholes rho per 1.00 rate point."""

    right = _right(option_type)
    if maturity <= 0.0 or volatility <= _MIN_VOL:
        return 0.0
    _, d2 = _d1_d2(spot, strike, maturity, rate, volatility, dividend)
    if right == "call":
        return strike * maturity * math.exp(-rate * maturity) * normal_cdf(d2)
    return -strike * maturity * math.exp(-rate * maturity) * normal_cdf(-d2)


def put_call_parity_residual(
    call_price: float,
    put_price: float,
    spot: float,
    strike: float,
    maturity: float,
    rate: float,
    dividend: float = 0.0,
) -> float:
    """Return `C - P - (S e^-qT - K e^-rT)`."""

    return (
        call_price
        - put_price
        - (spot * math.exp(-dividend * maturity) - strike * math.exp(-rate * maturity))
    )


def implied_volatility(
    price: float,
    spot: float,
    strike: float,
    maturity: float,
    rate: float,
    option_type: str,
    dividend: float = 0.0,
    lower: float = _MIN_VOL,
    upper: float = 5.0,
    tolerance: float = 1e-8,
    max_iterations: int = 100,
) -> float:
    """Invert Black-Scholes price with robust bisection."""

    right = _right(option_type)
    if maturity <= 0.0:
        intrinsic = bs_price(spot, strike, maturity, rate, lower, right, dividend)
        return 0.0 if abs(price - intrinsic) <= tolerance else math.nan

    low_price = bs_price(spot, strike, maturity, rate, lower, right, dividend)
    if price < low_price - tolerance:
        return math.nan

    high = upper
    high_price = bs_price(spot, strike, maturity, rate, high, right, dividend)
    while high_price < price and high < 10.0:
        high *= 2.0
        high_price = bs_price(spot, strike, maturity, rate, high, right, dividend)
    if price > high_price + tolerance:
        return math.nan

    low = lower
    for _ in range(max_iterations):
        mid = 0.5 * (low + high)
        mid_price = bs_price(spot, strike, maturity, rate, mid, right, dividend)
        if high - low <= 1e-10:
            return mid
        if mid_price > price:
            high = mid
        else:
            low = mid
    return 0.5 * (low + high)
