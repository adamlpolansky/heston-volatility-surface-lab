"""Heston calibration routines."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

from heston_arb_lab.data.schemas import CalibrationResult
from heston_arb_lab.models.black_scholes import bs_vega
from heston_arb_lab.models.heston_cf import HestonParams
from heston_arb_lab.models.heston_pricer import heston_implied_volatility, heston_price
from heston_arb_lab.utils.validation import require_columns

Objective = Literal["price_rmse", "iv_rmse", "vega_weighted_price", "bid_ask_normalized"]
CalibrationMode = Literal[
    "full",
    "regularized",
    "fixed_theta",
    "fixed_kappa_theta",
    "fixed_kappa_theta_sigma",
]


@dataclass(frozen=True)
class CalibrationConfig:
    """Numerical calibration settings."""

    objective: Objective = "price_rmse"
    mode: CalibrationMode = "full"
    seed: int = 7
    maxiter: int = 8
    popsize: int = 5
    polish: bool = False
    feller_penalty: float = 0.0
    prior_penalty: float = 0.0
    boundary_penalty: float = 0.0
    fixed_theta: float | None = None
    fixed_kappa: float | None = None
    fixed_sigma: float | None = None
    prior_v0: float | None = None
    prior_theta: float | None = None
    prior_kappa: float = 2.0
    prior_sigma: float = 0.6
    prior_rho: float = -0.35


DEFAULT_BOUNDS: tuple[tuple[float, float], ...] = (
    (0.005, 0.50),  # v0
    (0.005, 0.50),  # theta
    (0.10, 8.00),  # kappa
    (0.001, 2.00),  # sigma
    (-0.95, 0.95),  # rho
)

CALIBRATION_PENALTY = 1e6
MIN_DENOMINATOR = 1e-3
BOUNDARY_EPS = 1e-6


def _params_from_array(values: np.ndarray) -> HestonParams:
    return HestonParams(
        v0=float(values[0]),
        theta=float(values[1]),
        kappa=float(values[2]),
        sigma=float(values[3]),
        rho=float(values[4]),
    )


def _estimate_variance_prior(market: pd.DataFrame, fallback: float = 0.04) -> float:
    if {"implied_vol", "time_to_expiry"}.issubset(market.columns):
        iv = pd.to_numeric(market["implied_vol"], errors="coerce")
        maturity = pd.to_numeric(market["time_to_expiry"], errors="coerce")
        values = (iv * iv).where(maturity > 0).dropna()
        if not values.empty:
            return float(np.clip(values.median(), 0.005, 0.50))
    return fallback


def _free_parameter_names(mode: CalibrationMode) -> list[str]:
    if mode in {"fixed_kappa_theta", "fixed_kappa_theta_sigma"}:
        return ["v0", "sigma", "rho"] if mode == "fixed_kappa_theta" else ["v0", "rho"]
    if mode == "fixed_theta":
        return ["v0", "kappa", "sigma", "rho"]
    return ["v0", "theta", "kappa", "sigma", "rho"]


def _values_to_params(
    values: np.ndarray,
    *,
    mode: CalibrationMode,
    free_names: list[str],
    cfg: CalibrationConfig,
    theta_prior: float,
) -> HestonParams:
    params = {
        "v0": cfg.prior_v0 or theta_prior,
        "theta": cfg.fixed_theta or theta_prior,
        "kappa": cfg.fixed_kappa or cfg.prior_kappa,
        "sigma": cfg.fixed_sigma or cfg.prior_sigma,
        "rho": cfg.prior_rho,
    }
    params.update({name: float(value) for name, value in zip(free_names, values, strict=True)})
    if mode == "fixed_theta":
        params["theta"] = cfg.fixed_theta or theta_prior
    elif mode == "fixed_kappa_theta":
        params["theta"] = cfg.fixed_theta or theta_prior
        params["kappa"] = cfg.fixed_kappa or cfg.prior_kappa
    elif mode == "fixed_kappa_theta_sigma":
        params["theta"] = cfg.fixed_theta or theta_prior
        params["kappa"] = cfg.fixed_kappa or cfg.prior_kappa
        params["sigma"] = cfg.fixed_sigma or cfg.prior_sigma
    return HestonParams(**params)


def _reduced_bounds(
    bounds: tuple[tuple[float, float], ...], free_names: list[str]
) -> tuple[tuple[float, float], ...]:
    order = ["v0", "theta", "kappa", "sigma", "rho"]
    by_name = dict(zip(order, bounds, strict=True))
    return tuple(by_name[name] for name in free_names)


def heston_boundary_penalty(
    params: HestonParams,
    bounds: tuple[tuple[float, float], ...] = DEFAULT_BOUNDS,
) -> float:
    """Return a smooth penalty that rises near parameter bounds."""

    values = np.asarray(
        [params.v0, params.theta, params.kappa, params.sigma, params.rho], dtype=float
    )
    penalty = 0.0
    for value, (low, high) in zip(values, bounds, strict=True):
        width = max(high - low, BOUNDARY_EPS)
        distance = min(value - low, high - value) / width
        if distance < 0.10:
            penalty += float((0.10 - max(distance, 0.0)) ** 2)
    return penalty


def heston_prior_penalty(
    params: HestonParams,
    *,
    cfg: CalibrationConfig,
    theta_prior: float,
) -> float:
    """Return soft prior penalty for weakly identified Heston parameters."""

    priors = {
        "v0": cfg.prior_v0 or theta_prior,
        "theta": cfg.prior_theta or theta_prior,
        "kappa": cfg.prior_kappa,
        "sigma": cfg.prior_sigma,
        "rho": cfg.prior_rho,
    }
    scales = {"v0": 0.10, "theta": 0.10, "kappa": 2.0, "sigma": 0.6, "rho": 0.45}
    return float(
        sum(((getattr(params, name) - prior) / scales[name]) ** 2 for name, prior in priors.items())
    )


def _market_price(row: pd.Series) -> float:
    if "price" in row and pd.notna(row["price"]):
        return float(row["price"])
    return float(row["mid"])


def _finite_or_penalty(value: float) -> float:
    return value if np.isfinite(value) else CALIBRATION_PENALTY


def _safe_spread_denominator(row: pd.Series, market_price: float) -> float:
    ask = float(row.get("ask", market_price))
    bid = float(row.get("bid", market_price))
    spread = ask - bid
    if not np.isfinite(spread) or spread <= 0.0:
        spread = float(row.get("spread", 0.0))
    return max(abs(spread), MIN_DENOMINATOR)


def calibration_residuals(
    market: pd.DataFrame,
    *,
    spot: float,
    rate: float,
    dividend: float,
    params: HestonParams,
    objective: Objective,
) -> np.ndarray:
    """Return model residuals for a market surface dataframe."""

    residuals: list[float] = []
    for _, row in market.iterrows():
        try:
            strike = float(row["strike"])
            maturity = float(row["time_to_expiry"])
            right = str(row["right"])
            market_price = _market_price(row)
        except (TypeError, ValueError, KeyError):
            residuals.append(CALIBRATION_PENALTY)
            continue
        if (
            not np.isfinite(strike)
            or not np.isfinite(maturity)
            or maturity <= 0.0
            or not np.isfinite(market_price)
            or market_price <= 0.0
        ):
            residuals.append(CALIBRATION_PENALTY)
            continue
        try:
            model_price = heston_price(spot, strike, maturity, rate, params, right, dividend)
        except (ArithmeticError, ValueError, FloatingPointError, OverflowError):
            residuals.append(CALIBRATION_PENALTY)
            continue
        if not np.isfinite(model_price) or model_price < 0.0:
            residuals.append(CALIBRATION_PENALTY)
            continue

        if objective == "iv_rmse":
            try:
                market_iv = float(row["implied_vol"])
                model_iv = heston_implied_volatility(
                    spot, strike, maturity, rate, params, right, dividend
                )
            except (ArithmeticError, ValueError, FloatingPointError, OverflowError, KeyError):
                residuals.append(CALIBRATION_PENALTY)
                continue
            if not np.isfinite(market_iv) or not np.isfinite(model_iv):
                residuals.append(CALIBRATION_PENALTY)
                continue
            residuals.append(_finite_or_penalty(model_iv - market_iv))
        elif objective == "vega_weighted_price":
            try:
                volatility = max(float(row.get("implied_vol", 0.2)), 1e-4)
                vega = bs_vega(spot, strike, maturity, rate, volatility, dividend)
            except (ArithmeticError, ValueError, FloatingPointError, OverflowError):
                vega = MIN_DENOMINATOR
            denominator = max(abs(vega), MIN_DENOMINATOR)
            residuals.append(_finite_or_penalty((model_price - market_price) / denominator))
        elif objective == "bid_ask_normalized":
            denominator = _safe_spread_denominator(row, market_price)
            residuals.append(_finite_or_penalty((model_price - market_price) / denominator))
        else:
            residuals.append(_finite_or_penalty(model_price - market_price))
    return np.asarray(residuals, dtype=float)


def calibrate_heston(
    market: pd.DataFrame,
    *,
    spot: float,
    rate: float,
    dividend: float = 0.0,
    config: CalibrationConfig | None = None,
    bounds: tuple[tuple[float, float], ...] = DEFAULT_BOUNDS,
) -> CalibrationResult:
    """Calibrate Heston parameters to a cleaned surface."""

    require_columns(market, ["strike", "time_to_expiry", "right"], "market surface")
    if "price" not in market.columns and "mid" not in market.columns:
        raise ValueError("market surface must contain either `price` or `mid`")
    cfg = config or CalibrationConfig()
    if cfg.mode not in {
        "full",
        "regularized",
        "fixed_theta",
        "fixed_kappa_theta",
        "fixed_kappa_theta_sigma",
    }:
        raise ValueError(f"unsupported Heston calibration mode: {cfg.mode}")
    theta_prior = cfg.prior_theta or cfg.fixed_theta or _estimate_variance_prior(market)
    free_names = _free_parameter_names(cfg.mode)
    optimizer_bounds = _reduced_bounds(bounds, free_names)

    def objective_fn(values: np.ndarray) -> float:
        params = (
            _params_from_array(values)
            if cfg.mode in {"full", "regularized"}
            else _values_to_params(
                values,
                mode=cfg.mode,
                free_names=free_names,
                cfg=cfg,
                theta_prior=theta_prior,
            )
        )
        residuals = calibration_residuals(
            market,
            spot=spot,
            rate=rate,
            dividend=dividend,
            params=params,
            objective=cfg.objective,
        )
        if residuals.size == 0:
            return CALIBRATION_PENALTY
        residuals = residuals[np.isfinite(residuals)]
        if residuals.size == 0:
            return CALIBRATION_PENALTY
        loss = float(np.mean(residuals * residuals))
        if not np.isfinite(loss):
            return CALIBRATION_PENALTY
        if cfg.feller_penalty > 0 and params.feller_margin < 0:
            loss += cfg.feller_penalty * abs(params.feller_margin)
        if cfg.prior_penalty > 0:
            loss += cfg.prior_penalty * heston_prior_penalty(
                params, cfg=cfg, theta_prior=theta_prior
            )
        if cfg.boundary_penalty > 0:
            loss += cfg.boundary_penalty * heston_boundary_penalty(params, bounds)
        return loss

    try:
        from scipy.optimize import differential_evolution, minimize
    except ImportError:
        rng = np.random.default_rng(cfg.seed)
        midpoint = np.asarray([(low + high) / 2.0 for low, high in optimizer_bounds], dtype=float)
        candidates = [midpoint]
        for _ in range(max(cfg.maxiter * cfg.popsize, 5)):
            candidates.append(
                np.asarray([rng.uniform(low, high) for low, high in optimizer_bounds], dtype=float)
            )
        scored = [(objective_fn(candidate), candidate) for candidate in candidates]
        best_loss, best_values = min(scored, key=lambda item: item[0])
        optimizer_success = False
    else:
        global_result = differential_evolution(
            objective_fn,
            bounds=optimizer_bounds,
            seed=cfg.seed,
            maxiter=cfg.maxiter,
            popsize=cfg.popsize,
            polish=cfg.polish,
            updating="immediate",
            workers=1,
        )
        if cfg.maxiter <= 1 and not cfg.polish:
            best_values = global_result.x
            best_loss = float(global_result.fun)
            optimizer_success = bool(global_result.success)
        else:
            local_result = minimize(
                objective_fn,
                global_result.x,
                method="L-BFGS-B",
                bounds=optimizer_bounds,
                options={"maxiter": 50},
            )
            best_values = (
                local_result.x if local_result.fun <= global_result.fun else global_result.x
            )
            best_loss = min(float(local_result.fun), float(global_result.fun))
            optimizer_success = bool(local_result.success or global_result.success)
    params = (
        _params_from_array(best_values)
        if cfg.mode in {"full", "regularized"}
        else _values_to_params(
            best_values,
            mode=cfg.mode,
            free_names=free_names,
            cfg=cfg,
            theta_prior=theta_prior,
        )
    )
    residuals = calibration_residuals(
        market,
        spot=spot,
        rate=rate,
        dividend=dividend,
        params=params,
        objective=cfg.objective,
    )
    finite_residuals = residuals[np.isfinite(residuals)]
    if finite_residuals.size == 0:
        finite_residuals = np.asarray([CALIBRATION_PENALTY], dtype=float)
    return CalibrationResult(
        params=params.as_dict(),
        loss=best_loss,
        objective=cfg.objective,
        diagnostics={
            "mode": cfg.mode,
            "feller_margin": params.feller_margin,
            "feller_penalty_contribution": (
                cfg.feller_penalty * abs(params.feller_margin)
                if cfg.feller_penalty > 0 and params.feller_margin < 0
                else 0.0
            ),
            "prior_penalty_contribution": (
                cfg.prior_penalty * heston_prior_penalty(params, cfg=cfg, theta_prior=theta_prior)
            ),
            "boundary_penalty_contribution": (
                cfg.boundary_penalty * heston_boundary_penalty(params, bounds)
            ),
            "fixed_theta": cfg.fixed_theta
            or (theta_prior if "theta" not in free_names else np.nan),
            "fixed_kappa": cfg.fixed_kappa if "kappa" not in free_names else np.nan,
            "fixed_sigma": cfg.fixed_sigma if "sigma" not in free_names else np.nan,
            "residual_mean": float(np.mean(finite_residuals)),
            "residual_std": float(np.std(finite_residuals)),
            "n_points": len(market),
            "optimizer_success": optimizer_success,
        },
    )
