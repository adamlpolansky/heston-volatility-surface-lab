from __future__ import annotations

import math
from datetime import date

import pandas as pd
import pytest

from heston_arb_lab.models.ssvi import (
    SSVIParams,
    fit_ssvi_to_surface,
    ssvi_implied_vol,
    ssvi_power_law_phi,
    ssvi_sufficient_conditions,
    ssvi_total_variance,
)


def test_ssvi_total_variance_positive_for_valid_params() -> None:
    variance = ssvi_total_variance(0.05, theta=0.04, rho=-0.4, phi=2.0)

    assert variance > 0.0


def test_ssvi_implied_vol_is_finite_for_valid_params() -> None:
    iv = ssvi_implied_vol(0.05, ttm=0.25, theta=0.04, rho=-0.4, phi=2.0)

    assert math.isfinite(iv)
    assert iv > 0.0


def test_ssvi_invalid_domain_rejected() -> None:
    with pytest.raises(ValueError, match="rho"):
        ssvi_total_variance(0.0, theta=0.04, rho=1.0, phi=2.0)
    with pytest.raises(ValueError, match="eta"):
        ssvi_power_law_phi(theta=0.04, eta=0.0, gamma=0.5)
    with pytest.raises(ValueError, match="gamma"):
        ssvi_power_law_phi(theta=0.04, eta=1.0, gamma=1.5)


def test_ssvi_sufficient_conditions_return_pass_fail_rows() -> None:
    params = SSVIParams(
        rho=0.95,
        eta=10.0,
        gamma=0.0,
        theta_by_expiry={"2040-07-08": 0.5, "2040-07-15": 0.4},
    )

    diagnostics = ssvi_sufficient_conditions(params)

    assert {"check_name", "status", "value", "threshold", "message"}.issubset(diagnostics.columns)
    assert "fail" in set(diagnostics["status"])
    assert "warning" in set(diagnostics["status"])


def test_ssvi_fit_runs_on_synthetic_tiny_surface_and_improves_loss() -> None:
    surface = _synthetic_surface()

    result = fit_ssvi_to_surface(surface, min_expiries=2, min_strikes=3)

    assert result.fit["ssvi_iv"].notna().all()
    assert result.final_loss <= result.initial_loss
    assert result.diagnostics["check_name"].str.contains("butterfly").any()


def test_ssvi_fit_skips_with_clear_reason_on_insufficient_strikes() -> None:
    surface = _synthetic_surface()
    surface = surface[surface["strike"].eq(surface["strike"].min())].copy()

    with pytest.raises(ValueError, match="strikes"):
        fit_ssvi_to_surface(surface, min_expiries=2, min_strikes=3)


def _synthetic_surface() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for expiration, ttm, base_iv in (
        (date(2040, 7, 8), 7 / 365, 0.42),
        (date(2040, 7, 15), 14 / 365, 0.40),
    ):
        for strike in (395.0, 400.0, 405.0, 410.0, 415.0):
            log_moneyness = math.log(strike / 405.0)
            iv = base_iv + 0.8 * abs(log_moneyness)
            for right in ("call", "put"):
                rows.append(
                    {
                        "symbol": "SYNTH",
                        "snapshot_ts": pd.Timestamp("2040-07-01T14:00:00Z"),
                        "expiration": expiration,
                        "strike": strike,
                        "right": right,
                        "ttm": ttm,
                        "time_to_expiry": ttm,
                        "iv_mid": iv,
                        "implied_vol": iv,
                        "log_moneyness": log_moneyness,
                        "spread_pct_mid": 0.03,
                    }
                )
    return pd.DataFrame(rows)
