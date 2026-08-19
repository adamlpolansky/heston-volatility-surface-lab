"""Heston option pricing."""

from __future__ import annotations

import math
import warnings
from importlib.util import find_spec

from heston_arb_lab.models.black_scholes import bs_price, implied_volatility
from heston_arb_lab.models.heston_cf import (
    HestonParams,
    average_variance,
    heston_characteristic_function,
)


def _probability_integrand(
    u: float,
    probability: int,
    spot: float,
    strike: float,
    maturity: float,
    rate: float,
    dividend: float,
    params: HestonParams,
) -> float:
    complex_u = complex(u, 0.0)
    exponent = complex(0.0, -u * math.log(strike))
    if probability == 1:
        numerator = heston_characteristic_function(
            complex_u - 1j,
            spot=spot,
            maturity=maturity,
            rate=rate,
            dividend=dividend,
            params=params,
        )
        denominator = (
            1j
            * complex_u
            * heston_characteristic_function(
                -1j,
                spot=spot,
                maturity=maturity,
                rate=rate,
                dividend=dividend,
                params=params,
            )
        )
    else:
        numerator = heston_characteristic_function(
            complex_u,
            spot=spot,
            maturity=maturity,
            rate=rate,
            dividend=dividend,
            params=params,
        )
        denominator = 1j * complex_u
    return (
        complex(math.cos(exponent.imag), math.sin(exponent.imag)) * numerator / denominator
    ).real


def _risk_neutral_probability(
    probability: int,
    *,
    spot: float,
    strike: float,
    maturity: float,
    rate: float,
    dividend: float,
    params: HestonParams,
    integration_limit: float = 100.0,
) -> float:
    try:
        from scipy.integrate import IntegrationWarning, quad
    except ImportError as exc:
        raise RuntimeError(
            "SciPy is required for full Heston Fourier integration. Install project dependencies "
            "or use near-constant variance parameters for the Black-Scholes fallback."
        ) from exc

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", IntegrationWarning)
        integral = float(
            quad(
                _probability_integrand,
                1e-8,
                integration_limit,
                args=(probability, spot, strike, maturity, rate, dividend, params),
                epsabs=1e-7,
                epsrel=1e-7,
                limit=200,
            )[0]
        )
    return min(max(0.5 + integral / math.pi, 0.0), 1.0)


def heston_call_price(
    spot: float,
    strike: float,
    maturity: float,
    rate: float,
    params: HestonParams,
    dividend: float = 0.0,
) -> float:
    """Price a European call under the Heston model."""

    if maturity <= 0.0:
        return max(spot - strike, 0.0)
    if params.sigma <= 1e-6 or find_spec("scipy") is None:
        vol = math.sqrt(max(average_variance(params, maturity), 1e-12))
        return bs_price(spot, strike, maturity, rate, vol, "call", dividend)

    p1 = _risk_neutral_probability(
        1,
        spot=spot,
        strike=strike,
        maturity=maturity,
        rate=rate,
        dividend=dividend,
        params=params,
    )
    p2 = _risk_neutral_probability(
        2,
        spot=spot,
        strike=strike,
        maturity=maturity,
        rate=rate,
        dividend=dividend,
        params=params,
    )
    price = spot * math.exp(-dividend * maturity) * p1 - strike * math.exp(-rate * maturity) * p2
    upper = spot * math.exp(-dividend * maturity)
    intrinsic = max(
        spot * math.exp(-dividend * maturity) - strike * math.exp(-rate * maturity), 0.0
    )
    return min(max(price, intrinsic), upper)


def heston_price(
    spot: float,
    strike: float,
    maturity: float,
    rate: float,
    params: HestonParams,
    option_type: str,
    dividend: float = 0.0,
) -> float:
    """Price a European call or put under Heston."""

    right = option_type.lower()
    call = heston_call_price(spot, strike, maturity, rate, params, dividend)
    if right in {"call", "c"}:
        return call
    if right in {"put", "p"}:
        return call - spot * math.exp(-dividend * maturity) + strike * math.exp(-rate * maturity)
    raise ValueError("option_type must be call or put")


def heston_implied_volatility(
    spot: float,
    strike: float,
    maturity: float,
    rate: float,
    params: HestonParams,
    option_type: str,
    dividend: float = 0.0,
) -> float:
    """Convert a Heston price into a Black-Scholes implied volatility."""

    price = heston_price(spot, strike, maturity, rate, params, option_type, dividend)
    return implied_volatility(price, spot, strike, maturity, rate, option_type, dividend)
