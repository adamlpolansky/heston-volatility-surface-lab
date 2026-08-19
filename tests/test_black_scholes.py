from __future__ import annotations

import math

import pytest

from heston_arb_lab.models.black_scholes import (
    bs_delta,
    bs_gamma,
    bs_price,
    implied_volatility,
    put_call_parity_residual,
)


def test_put_call_parity() -> None:
    call = bs_price(100.0, 100.0, 0.5, 0.03, 0.2, "call", 0.01)
    put = bs_price(100.0, 100.0, 0.5, 0.03, 0.2, "put", 0.01)
    residual = put_call_parity_residual(call, put, 100.0, 100.0, 0.5, 0.03, 0.01)
    assert abs(residual) < 1e-10


@pytest.mark.parametrize("strike", [80.0, 95.0, 100.0, 110.0, 125.0])
@pytest.mark.parametrize("maturity", [0.05, 0.5, 2.0])
def test_implied_volatility_roundtrip(strike: float, maturity: float) -> None:
    price = bs_price(100.0, strike, maturity, 0.02, 0.24, "call")
    iv = implied_volatility(price, 100.0, strike, maturity, 0.02, "call")
    assert iv == pytest.approx(0.24, abs=1e-6)


def test_price_monotonicity_with_spot_and_vol() -> None:
    low_spot = bs_price(95.0, 100.0, 1.0, 0.02, 0.2, "call")
    high_spot = bs_price(105.0, 100.0, 1.0, 0.02, 0.2, "call")
    low_vol = bs_price(100.0, 100.0, 1.0, 0.02, 0.1, "call")
    high_vol = bs_price(100.0, 100.0, 1.0, 0.02, 0.3, "call")
    assert high_spot > low_spot
    assert high_vol > low_vol


def test_delta_and_gamma_finite_difference_smoke() -> None:
    spot = 100.0
    bump = 0.01
    up = bs_price(spot + bump, 100.0, 0.75, 0.03, 0.22, "call")
    mid = bs_price(spot, 100.0, 0.75, 0.03, 0.22, "call")
    down = bs_price(spot - bump, 100.0, 0.75, 0.03, 0.22, "call")
    fd_delta = (up - down) / (2.0 * bump)
    fd_gamma = (up - 2.0 * mid + down) / (bump * bump)
    assert bs_delta(spot, 100.0, 0.75, 0.03, 0.22, "call") == pytest.approx(fd_delta, rel=1e-4)
    assert bs_gamma(spot, 100.0, 0.75, 0.03, 0.22) == pytest.approx(fd_gamma, rel=1e-3)
    assert math.isfinite(fd_delta)
    assert math.isfinite(fd_gamma)
