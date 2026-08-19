"""Heston characteristic function."""

from __future__ import annotations

import cmath
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class HestonParams:
    """Risk-neutral Heston parameters."""

    v0: float
    theta: float
    kappa: float
    sigma: float
    rho: float

    def __post_init__(self) -> None:
        if self.v0 < 0 or self.theta < 0:
            raise ValueError("v0 and theta must be non-negative")
        if self.kappa <= 0:
            raise ValueError("kappa must be positive")
        if self.sigma < 0:
            raise ValueError("sigma must be non-negative")
        if not -0.999 <= self.rho <= 0.999:
            raise ValueError("rho must be in [-0.999, 0.999]")

    @property
    def feller_margin(self) -> float:
        """Return `2*kappa*theta - sigma^2`."""

        return 2.0 * self.kappa * self.theta - self.sigma * self.sigma

    def as_dict(self) -> dict[str, float]:
        """Return a JSON-serializable parameter dictionary."""

        return {
            "v0": self.v0,
            "theta": self.theta,
            "kappa": self.kappa,
            "sigma": self.sigma,
            "rho": self.rho,
        }


def average_variance(params: HestonParams, maturity: float) -> float:
    """Return expected average variance under mean reversion."""

    if maturity <= 0:
        return max(params.v0, 0.0)
    if params.kappa <= 1e-12:
        return max(params.v0, 0.0)
    integrated = (
        params.theta * maturity
        + (params.v0 - params.theta) * (1.0 - math.exp(-params.kappa * maturity)) / params.kappa
    )
    return max(integrated / maturity, 0.0)


def heston_characteristic_function(
    u: complex,
    *,
    spot: float,
    maturity: float,
    rate: float,
    dividend: float,
    params: HestonParams,
) -> complex:
    """Evaluate the log-price characteristic function under Heston dynamics."""

    if maturity <= 0:
        return cmath.exp(1j * u * math.log(spot))

    if params.sigma <= 1e-10:
        avg_var = average_variance(params, maturity)
        variance = avg_var * maturity
        drift = math.log(spot) + (rate - dividend) * maturity - 0.5 * variance
        return cmath.exp(1j * u * drift - 0.5 * u * u * variance)

    iu = 1j * u
    sigma2 = params.sigma * params.sigma
    b = params.kappa
    d = cmath.sqrt((params.rho * params.sigma * iu - b) ** 2 + sigma2 * (iu + u * u))
    numerator = b - params.rho * params.sigma * iu - d
    denominator = b - params.rho * params.sigma * iu + d
    g = numerator / denominator
    exp_dt = cmath.exp(-d * maturity)
    log_term = cmath.log((1.0 - g * exp_dt) / (1.0 - g))
    c_term = (rate - dividend) * iu * maturity + (params.kappa * params.theta / sigma2) * (
        numerator * maturity - 2.0 * log_term
    )
    d_term = (numerator / sigma2) * ((1.0 - exp_dt) / (1.0 - g * exp_dt))
    return cmath.exp(iu * math.log(spot) + c_term + d_term * params.v0)
