"""SSVI baseline helpers for sparse real-surface diagnostics."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, cast

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SSVIParams:
    """Tiny-surface SSVI parameters with per-expiry ATM total variance."""

    rho: float
    eta: float
    gamma: float
    theta_by_expiry: dict[str, float]

    def __post_init__(self) -> None:
        validate_ssvi_domain(self.rho, self.eta, self.gamma)
        if not self.theta_by_expiry:
            raise ValueError("theta_by_expiry must not be empty")
        for expiry, theta in self.theta_by_expiry.items():
            if not math.isfinite(float(theta)) or float(theta) <= 0.0:
                raise ValueError(f"theta must be positive for expiry {expiry}")

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON/parquet-friendly parameter dictionary."""

        return {
            "rho": self.rho,
            "eta": self.eta,
            "gamma": self.gamma,
            "theta_by_expiry": self.theta_by_expiry,
        }


@dataclass(frozen=True)
class SSVIFitResult:
    """Fit result for one SSVI snapshot."""

    params: SSVIParams
    fit: pd.DataFrame
    diagnostics: pd.DataFrame
    initial_loss: float
    final_loss: float
    optimizer_success: bool
    message: str


def validate_ssvi_domain(rho: float, eta: float, gamma: float) -> None:
    """Validate the global SSVI parameter domain."""

    if not math.isfinite(float(rho)) or not -1.0 < float(rho) < 1.0:
        raise ValueError("rho must be in (-1, 1)")
    if not math.isfinite(float(eta)) or float(eta) <= 0.0:
        raise ValueError("eta must be positive")
    if not math.isfinite(float(gamma)) or not 0.0 <= float(gamma) <= 1.0:
        raise ValueError("gamma must be in [0, 1]")


def ssvi_total_variance(
    k: float | np.ndarray | pd.Series, theta: float, rho: float, phi: float
) -> float | np.ndarray:
    """Return SSVI total implied variance at log-moneyness ``k``."""

    if not math.isfinite(float(theta)) or float(theta) <= 0.0:
        raise ValueError("theta must be positive")
    if not math.isfinite(float(rho)) or not -1.0 < float(rho) < 1.0:
        raise ValueError("rho must be in (-1, 1)")
    if not math.isfinite(float(phi)) or float(phi) <= 0.0:
        raise ValueError("phi must be positive")
    k_array = np.asarray(k, dtype=float)
    inside = (phi * k_array + rho) ** 2 + 1.0 - rho * rho
    variance = theta * 0.5 * (1.0 + rho * phi * k_array + np.sqrt(np.maximum(inside, 0.0)))
    variance = np.maximum(variance, 0.0)
    if np.isscalar(k):
        return float(variance)
    return variance


def ssvi_implied_vol(
    k: float | np.ndarray | pd.Series,
    ttm: float | np.ndarray | pd.Series,
    theta: float,
    rho: float,
    phi: float,
) -> float | np.ndarray:
    """Return Black-Scholes implied volatility from SSVI total variance."""

    ttm_array = np.asarray(ttm, dtype=float)
    if np.any(ttm_array <= 0.0) or np.any(~np.isfinite(ttm_array)):
        raise ValueError("ttm must be positive and finite")
    total_variance = np.asarray(ssvi_total_variance(k, theta, rho, phi), dtype=float)
    iv = np.sqrt(np.maximum(total_variance, 0.0) / ttm_array)
    if np.isscalar(k) and np.isscalar(ttm):
        return float(iv)
    return cast(np.ndarray, iv)


def ssvi_power_law_phi(theta: float, eta: float, gamma: float) -> float:
    """Return the power-law SSVI shape function ``eta * theta ** (-gamma)``."""

    validate_ssvi_domain(0.0, eta, gamma)
    if not math.isfinite(float(theta)) or float(theta) <= 0.0:
        raise ValueError("theta must be positive")
    return float(eta * float(theta) ** (-float(gamma)))


def ssvi_total_variance_power_law(
    k: float | np.ndarray | pd.Series,
    ttm: float | np.ndarray | pd.Series,
    params: SSVIParams,
    *,
    expiry: str | None = None,
) -> float | np.ndarray:
    """Return SSVI total variance using per-expiry theta and power-law phi."""

    del ttm
    if expiry is None:
        if len(params.theta_by_expiry) != 1:
            raise ValueError("expiry is required when multiple theta values are present")
        theta = next(iter(params.theta_by_expiry.values()))
    else:
        theta = params.theta_by_expiry[str(expiry)]
    phi = ssvi_power_law_phi(theta, params.eta, params.gamma)
    return ssvi_total_variance(k, theta, params.rho, phi)


def ssvi_sufficient_conditions(params: SSVIParams) -> pd.DataFrame:
    """Return sufficient SSVI static-arbitrage sanity diagnostics."""

    rows: list[dict[str, Any]] = []
    rho = params.rho
    rows.append(
        {
            "check_name": "rho_domain",
            "status": "pass" if -1.0 < rho < 1.0 else "fail",
            "value": rho,
            "threshold": "(-1, 1)",
            "message": "SSVI rho domain check.",
        }
    )
    ordered = sorted(params.theta_by_expiry.items(), key=lambda item: item[0])
    previous_theta: float | None = None
    calendar_ok = True
    for expiry, theta in params.theta_by_expiry.items():
        phi = ssvi_power_law_phi(theta, params.eta, params.gamma)
        product = theta * phi * (1.0 + abs(rho))
        square_product = theta * phi * phi * (1.0 + abs(rho))
        rows.extend(
            [
                {
                    "check_name": f"theta_positive:{expiry}",
                    "status": "pass" if theta > 0.0 else "fail",
                    "value": theta,
                    "threshold": "> 0",
                    "message": "ATM total variance must be positive.",
                },
                {
                    "check_name": f"phi_positive:{expiry}",
                    "status": "pass" if phi > 0.0 else "fail",
                    "value": phi,
                    "threshold": "> 0",
                    "message": "SSVI phi(theta) must be positive.",
                },
                {
                    "check_name": f"butterfly_linear:{expiry}",
                    "status": "pass" if product < 4.0 else "fail",
                    "value": product,
                    "threshold": "< 4",
                    "message": "Sufficient SSVI butterfly condition.",
                },
                {
                    "check_name": f"butterfly_square:{expiry}",
                    "status": "pass" if square_product <= 4.0 else "fail",
                    "value": square_product,
                    "threshold": "<= 4",
                    "message": "Sufficient SSVI butterfly condition.",
                },
            ]
        )
    for _, theta in ordered:
        if previous_theta is not None and theta + 1e-12 < previous_theta:
            calendar_ok = False
        previous_theta = theta
    rows.append(
        {
            "check_name": "calendar_theta_monotonicity",
            "status": "pass" if calendar_ok else "warning",
            "value": "; ".join(f"{expiry}:{theta:.6g}" for expiry, theta in ordered),
            "threshold": "non-decreasing theta by maturity",
            "message": (
                "Calendar sufficient diagnostic; sparse tiny surfaces make this a caveat, "
                "not a complete proof."
            ),
        }
    )
    return pd.DataFrame(rows)


def fit_ssvi_to_surface(
    surface: pd.DataFrame, *, min_expiries: int = 2, min_strikes: int = 3
) -> SSVIFitResult:
    """Fit a tiny-surface SSVI baseline to one processed surface snapshot."""

    frame = _prepared_surface(surface)
    if frame.empty:
        raise ValueError("surface has no valid rows for SSVI")
    expiry_count = frame["expiry_key"].nunique()
    strike_count = frame["strike"].nunique()
    if expiry_count < min_expiries:
        raise ValueError(f"expiries {expiry_count} < required {min_expiries}")
    if strike_count < min_strikes:
        raise ValueError(f"strikes {strike_count} < required {min_strikes}")

    expiries = sorted(frame["expiry_key"].unique())
    initial_thetas = [
        max(
            float(frame.loc[frame["expiry_key"].eq(expiry), "observed_total_variance"].median()),
            1e-5,
        )
        for expiry in expiries
    ]
    initial = np.asarray([0.0, 1.0, 0.5, *initial_thetas], dtype=float)
    bounds = [(-0.95, 0.95), (0.001, 10.0), (0.0, 1.0), *[(1e-6, 5.0) for _ in expiries]]

    initial_loss = _ssvi_objective(initial, frame, expiries)
    try:
        from scipy.optimize import minimize
    except ImportError:
        result_x = initial
        final_loss = initial_loss
        success = False
        message = "SciPy unavailable; returned initial SSVI baseline"
    else:
        result = minimize(
            _ssvi_objective,
            initial,
            args=(frame, expiries),
            method="L-BFGS-B",
            bounds=bounds,
            options={"maxiter": 250},
        )
        result_x = result.x if np.isfinite(result.fun) else initial
        final_loss = float(result.fun) if np.isfinite(result.fun) else initial_loss
        success = bool(result.success)
        message = str(result.message)

    params = _params_from_vector(result_x, expiries)
    fit = _ssvi_fit_frame(frame, params)
    diagnostics = ssvi_sufficient_conditions(params)
    diagnostics["initial_loss"] = initial_loss
    diagnostics["final_loss"] = final_loss
    diagnostics["optimizer_success"] = success
    diagnostics["optimizer_message"] = message
    return SSVIFitResult(
        params=params,
        fit=fit,
        diagnostics=diagnostics,
        initial_loss=initial_loss,
        final_loss=final_loss,
        optimizer_success=success,
        message=message,
    )


def _prepared_surface(surface: pd.DataFrame) -> pd.DataFrame:
    required = {"expiration", "strike", "ttm"}
    if not required.issubset(surface.columns):
        return pd.DataFrame()
    frame = surface.copy()
    iv_col = "iv_mid" if "iv_mid" in frame.columns else "implied_vol"
    if iv_col not in frame:
        return pd.DataFrame()
    if "log_moneyness" not in frame:
        if "moneyness" in frame:
            frame["log_moneyness"] = np.log(pd.to_numeric(frame["moneyness"], errors="coerce"))
        elif {"strike", "underlying_price"}.issubset(frame.columns):
            frame["log_moneyness"] = np.log(
                pd.to_numeric(frame["strike"], errors="coerce")
                / pd.to_numeric(frame["underlying_price"], errors="coerce")
            )
        else:
            return pd.DataFrame()
    frame["iv_observed"] = pd.to_numeric(frame[iv_col], errors="coerce")
    frame["ttm"] = pd.to_numeric(frame["ttm"], errors="coerce")
    frame["strike"] = pd.to_numeric(frame["strike"], errors="coerce")
    frame["log_moneyness"] = pd.to_numeric(frame["log_moneyness"], errors="coerce")
    frame["observed_total_variance"] = frame["iv_observed"] ** 2 * frame["ttm"]
    spread = pd.to_numeric(frame.get("spread_pct_mid", 0.05), errors="coerce").fillna(0.05)
    frame["fit_weight"] = np.minimum(1.0 / (spread * spread + 1e-6), 10_000.0)
    frame["expiry_key"] = pd.to_datetime(frame["expiration"], errors="coerce").dt.date.astype(str)
    return (
        frame.dropna(
            subset=[
                "iv_observed",
                "ttm",
                "strike",
                "log_moneyness",
                "observed_total_variance",
                "expiry_key",
            ]
        )
        .query("iv_observed > 0 and ttm > 0 and observed_total_variance > 0")
        .copy()
    )


def _params_from_vector(values: np.ndarray, expiries: list[str]) -> SSVIParams:
    theta_by_expiry = {
        expiry: float(theta) for expiry, theta in zip(expiries, values[3:], strict=True)
    }
    return SSVIParams(
        rho=float(values[0]),
        eta=float(values[1]),
        gamma=float(values[2]),
        theta_by_expiry=theta_by_expiry,
    )


def _ssvi_objective(values: np.ndarray, frame: pd.DataFrame, expiries: list[str]) -> float:
    try:
        params = _params_from_vector(values, expiries)
    except ValueError:
        return 1e9
    fit = _ssvi_fit_frame(frame, params)
    residual = pd.to_numeric(fit["total_variance_residual"], errors="coerce")
    weights = pd.to_numeric(fit["fit_weight"], errors="coerce")
    if residual.empty or residual.isna().all():
        return 1e9
    loss = float(np.average(residual * residual, weights=weights))
    diagnostics = ssvi_sufficient_conditions(params)
    failures = int(diagnostics["status"].eq("fail").sum())
    warnings = int(diagnostics["status"].eq("warning").sum())
    return loss + failures * 10.0 + warnings * 0.1


def _ssvi_fit_frame(frame: pd.DataFrame, params: SSVIParams) -> pd.DataFrame:
    output = frame.copy()
    model_total_variance: list[float] = []
    for row in output.itertuples(index=False):
        theta = params.theta_by_expiry[str(row.expiry_key)]
        phi = ssvi_power_law_phi(theta, params.eta, params.gamma)
        model_total_variance.append(
            float(ssvi_total_variance(float(row.log_moneyness), theta, params.rho, phi))
        )
    output["ssvi_total_variance"] = model_total_variance
    output["ssvi_iv"] = np.sqrt(output["ssvi_total_variance"] / output["ttm"])
    output["iv_residual"] = output["iv_observed"] - output["ssvi_iv"]
    output["total_variance_residual"] = (
        output["observed_total_variance"] - output["ssvi_total_variance"]
    )
    return output
