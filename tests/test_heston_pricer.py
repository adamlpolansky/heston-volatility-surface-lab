from __future__ import annotations

import math

import pandas as pd
import pytest

from heston_arb_lab.models.black_scholes import bs_price
from heston_arb_lab.models.calibration import (
    CALIBRATION_PENALTY,
    CalibrationConfig,
    calibrate_heston,
    calibration_residuals,
)
from heston_arb_lab.models.heston_cf import HestonParams
from heston_arb_lab.models.heston_pricer import heston_call_price, heston_price


def test_heston_price_is_finite_and_non_negative() -> None:
    params = HestonParams(v0=0.04, theta=0.04, kappa=1.5, sigma=1e-12, rho=-0.4)
    price = heston_price(100.0, 105.0, 0.5, 0.03, params, "call")
    assert math.isfinite(price)
    assert price >= 0.0


def test_heston_fourier_call_and_put_prices_are_finite() -> None:
    params = HestonParams(v0=0.04, theta=0.04, kappa=1.5, sigma=0.35, rho=-0.4)

    call = heston_call_price(100.0, 105.0, 0.5, 0.03, params)
    call_via_dispatch = heston_price(100.0, 105.0, 0.5, 0.03, params, "call")
    put = heston_price(100.0, 105.0, 0.5, 0.03, params, "put")

    assert math.isfinite(call)
    assert math.isfinite(call_via_dispatch)
    assert math.isfinite(put)
    assert call >= 0.0
    assert put >= 0.0


def test_near_constant_variance_matches_black_scholes() -> None:
    params = HestonParams(v0=0.04, theta=0.04, kappa=2.0, sigma=1e-12, rho=0.0)
    heston = heston_price(100.0, 100.0, 1.0, 0.03, params, "call")
    black_scholes = bs_price(100.0, 100.0, 1.0, 0.03, 0.2, "call")
    assert heston == pytest.approx(black_scholes, abs=1e-8)


def test_calibration_output_is_serializable(synthetic_surface) -> None:
    market = synthetic_surface.head(6).copy()
    result = calibrate_heston(
        market,
        spot=100.0,
        rate=0.04,
        config=CalibrationConfig(maxiter=0, popsize=1, seed=1),
        bounds=((0.035, 0.045), (0.035, 0.045), (1.0, 1.2), (1e-12, 1e-6), (-0.1, 0.1)),
    )
    dumped = result.model_dump()
    assert dumped["loss"] >= 0.0
    assert set(dumped["params"]) == {"v0", "theta", "kappa", "sigma", "rho"}


def test_calibration_residuals_run_with_fourier_pricer() -> None:
    params = HestonParams(v0=0.04, theta=0.04, kappa=1.5, sigma=0.35, rho=-0.4)
    market = _tiny_market()

    residuals = calibration_residuals(
        market,
        spot=100.0,
        rate=0.03,
        dividend=0.0,
        params=params,
        objective="price_rmse",
    )

    assert residuals.shape == (len(market),)
    assert all(math.isfinite(value) for value in residuals)


def test_calibrate_heston_regression_no_quad_kwargs_type_error() -> None:
    market = _tiny_market()

    result = calibrate_heston(
        market,
        spot=100.0,
        rate=0.03,
        config=CalibrationConfig(maxiter=0, popsize=1, seed=1, polish=False),
        bounds=((0.035, 0.045), (0.035, 0.045), (1.0, 1.2), (0.25, 0.35), (-0.5, -0.3)),
    )

    assert result.loss >= 0.0
    assert result.diagnostics["n_points"] == len(market)


def test_calibration_residuals_penalize_singular_model_price(monkeypatch) -> None:
    def singular_price(*args, **kwargs):
        raise ZeroDivisionError("division by zero")

    monkeypatch.setattr("heston_arb_lab.models.calibration.heston_price", singular_price)
    params = HestonParams(v0=0.04, theta=0.04, kappa=1.5, sigma=0.35, rho=-0.4)

    residuals = calibration_residuals(
        _tiny_market(),
        spot=100.0,
        rate=0.03,
        dividend=0.0,
        params=params,
        objective="bid_ask_normalized",
    )

    assert residuals.shape == (3,)
    assert all(math.isfinite(value) for value in residuals)
    assert all(value == CALIBRATION_PENALTY for value in residuals)


def test_calibrate_heston_handles_zero_spread_rows() -> None:
    market = _tiny_market()
    market["bid"] = market["mid"]
    market["ask"] = market["mid"]

    result = calibrate_heston(
        market,
        spot=100.0,
        rate=0.03,
        config=CalibrationConfig(
            objective="bid_ask_normalized",
            maxiter=0,
            popsize=1,
            seed=1,
            polish=False,
        ),
        bounds=((0.035, 0.045), (0.035, 0.045), (1.0, 1.2), (1e-12, 1e-6), (-0.1, 0.1)),
    )

    assert math.isfinite(result.loss)
    assert result.loss >= 0.0


def _tiny_market() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "strike": 95.0,
                "time_to_expiry": 0.25,
                "right": "call",
                "mid": 7.0,
                "bid": 6.9,
                "ask": 7.1,
                "implied_vol": 0.25,
            },
            {
                "strike": 100.0,
                "time_to_expiry": 0.25,
                "right": "call",
                "mid": 4.0,
                "bid": 3.9,
                "ask": 4.1,
                "implied_vol": 0.25,
            },
            {
                "strike": 105.0,
                "time_to_expiry": 0.25,
                "right": "put",
                "mid": 6.0,
                "bid": 5.9,
                "ask": 6.1,
                "implied_vol": 0.25,
            },
        ]
    )
