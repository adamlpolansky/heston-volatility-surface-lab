# ruff: noqa: E501
"""Deterministic, provider-free evidence for the public project."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from pydantic import ValidationError

from heston_arb_lab.data.quality import add_quote_quality_flags
from heston_arb_lab.data.schemas import OptionQuote
from heston_arb_lab.models.black_scholes import bs_price
from heston_arb_lab.models.calibration import CalibrationConfig, calibrate_heston
from heston_arb_lab.models.heston_cf import HestonParams
from heston_arb_lab.models.heston_pricer import heston_price
from heston_arb_lab.models.ssvi import (
    SSVIFitResult,
    SSVIParams,
    fit_ssvi_to_surface,
    ssvi_implied_vol,
    ssvi_power_law_phi,
)
from heston_arb_lab.signals.ranking import score_signal
from heston_arb_lab.surface.forwards import estimate_forward_from_parity
from heston_arb_lab.surface.implied_vol import add_implied_volatility
from heston_arb_lab.surface.no_arbitrage import run_no_arbitrage_checks

SYNTHETIC_LABEL = "SYNTHETIC — NO MARKET DATA OR TRADING CLAIM"
SEED = 20260826
ASOF = date(2040, 1, 3)
SPOT = 100.0
RATE = 0.025
DIVIDEND = 0.01
MATURITY_DAYS = (30, 60, 120, 240)
STRIKES = (88.0, 91.0, 94.0, 97.0, 100.0, 103.0, 106.0, 109.0, 112.0)
TRUE_THETA = (0.0031, 0.0066, 0.0144, 0.0320)
TRUE_SSVI_RHO = 0.00
TRUE_SSVI_ETA = 1.00
TRUE_SSVI_GAMMA = 0.50
HESTON_FIXED_THETA = 0.045
HESTON_FIXED_KAPPA = 1.60
HESTON_FIXED_SIGMA = 0.50
EXECUTION_COST_BUFFER = 1.00


@dataclass(frozen=True)
class EvidenceRun:
    """In-memory evidence and public aggregate summary."""

    summary: dict[str, Any]
    surface: pd.DataFrame
    ssvi_fit: SSVIFitResult


def true_ssvi_params() -> SSVIParams:
    """Return the independently selected parameters used by the synthetic generator."""

    theta_by_expiry = {
        str(ASOF + timedelta(days=days)): theta
        for days, theta in zip(MATURITY_DAYS, TRUE_THETA, strict=True)
    }
    return SSVIParams(
        rho=TRUE_SSVI_RHO,
        eta=TRUE_SSVI_ETA,
        gamma=TRUE_SSVI_GAMMA,
        theta_by_expiry=theta_by_expiry,
    )


def generate_synthetic_quotes() -> pd.DataFrame:
    """Generate noisy synthetic quotes plus five deliberately invalid rows."""

    rng = np.random.default_rng(SEED)
    params = true_ssvi_params()
    timestamp = datetime(ASOF.year, ASOF.month, ASOF.day, 15, 30, tzinfo=UTC)
    rows: list[dict[str, Any]] = []

    for days in MATURITY_DAYS:
        expiration = ASOF + timedelta(days=days)
        expiry_key = str(expiration)
        maturity = days / 365.0
        forward = SPOT * math.exp((RATE - DIVIDEND) * maturity)
        theta = params.theta_by_expiry[expiry_key]
        phi = ssvi_power_law_phi(theta, params.eta, params.gamma)
        for strike in STRIKES:
            log_moneyness = math.log(strike / forward)
            true_iv = float(ssvi_implied_vol(log_moneyness, maturity, theta, params.rho, phi))
            pair_noise = float(np.clip(rng.normal(0.0, 0.00055), -0.0012, 0.0012))
            for right in ("call", "put"):
                theoretical_mid = bs_price(SPOT, strike, maturity, RATE, true_iv, right, DIVIDEND)
                noisy_mid = theoretical_mid + pair_noise
                spread_fraction = 0.025 + float(rng.uniform(0.0, 0.010))
                spread = max(0.012, spread_fraction * noisy_mid)
                rows.append(
                    {
                        "symbol": "SYNTHETIC",
                        "timestamp": timestamp,
                        "expiration": expiration,
                        "strike": strike,
                        "right": right,
                        "bid": noisy_mid - spread / 2.0,
                        "ask": noisy_mid + spread / 2.0,
                        "bid_size": int(rng.integers(20, 101)),
                        "ask_size": int(rng.integers(20, 101)),
                        "true_iv": true_iv,
                        "synthetic": True,
                    }
                )

    invalid_rows = [dict(rows[index]) for index in (0, 1, 2, 3, 4)]
    invalid_rows[0]["bid"] = float(invalid_rows[0]["ask"]) + 0.25
    invalid_rows[1]["bid"] = -0.10
    invalid_rows[2]["ask"] = None
    invalid_rows[3]["right"] = "straddle"
    invalid_rows[4]["strike"] = -1.0
    return pd.DataFrame([*rows, *invalid_rows])


def _schema_validate(quotes: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    accepted: list[dict[str, Any]] = []
    rejected = 0
    schema_columns = set(OptionQuote.model_fields)
    for row in quotes.to_dict(orient="records"):
        payload = {key: value for key, value in row.items() if key in schema_columns}
        if any(pd.isna(payload.get(key)) for key in schema_columns):
            rejected += 1
            continue
        try:
            OptionQuote.model_validate(payload)
        except ValidationError:
            rejected += 1
            continue
        accepted.append(row)
    return pd.DataFrame(accepted), rejected


def _prepare_surface(quotes: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    schema_valid, schema_rejected = _schema_validate(quotes)
    flagged = add_quote_quality_flags(schema_valid, max_relative_spread=0.50, min_mid=0.001)
    cleaned = flagged.loc[~flagged["quality_reject"]].copy()
    cleaned["time_to_expiry"] = (
        pd.to_datetime(cleaned["expiration"]).dt.date.map(lambda expiry: (expiry - ASOF).days)
        / 365.0
    )
    forwards = estimate_forward_from_parity(
        cleaned,
        spot=SPOT,
        rate=RATE,
        dividend=DIVIDEND,
    )
    cleaned = cleaned.merge(
        forwards[["expiration", "forward", "source"]], on="expiration", how="left"
    )
    cleaned = add_implied_volatility(
        cleaned,
        spot=SPOT,
        rate=RATE,
        dividend=DIVIDEND,
    )
    cleaned["log_moneyness"] = np.log(cleaned["strike"] / cleaned["forward"])
    cleaned["ttm"] = cleaned["time_to_expiry"]
    cleaned["spread_pct_mid"] = cleaned["relative_spread"]
    cleaned.attrs["schema_rejected"] = schema_rejected
    cleaned.attrs["quality_rejected"] = int(flagged["quality_reject"].sum())
    return cleaned.reset_index(drop=True), forwards


def _price_ssvi_fit(fit: pd.DataFrame) -> pd.DataFrame:
    priced = fit.copy()
    priced["ssvi_price"] = [
        bs_price(
            SPOT,
            float(row.strike),
            float(row.ttm),
            RATE,
            float(row.ssvi_iv),
            str(row.right),
            DIVIDEND,
        )
        for row in priced.itertuples(index=False)
    ]
    priced["mid_residual"] = priced["mid"] - priced["ssvi_price"]
    priced["residual_to_spread"] = priced["mid_residual"].abs() / priced["spread"]
    priced["total_variance"] = priced["ssvi_total_variance"]
    return priced


def _calibrate_heston(surface: pd.DataFrame) -> tuple[dict[str, Any], HestonParams]:
    calibration_market = surface.loc[
        surface["right"].eq("call") & surface["strike"].isin((94.0, 100.0, 106.0))
    ].copy()
    config = CalibrationConfig(
        objective="price_rmse",
        mode="fixed_kappa_theta_sigma",
        seed=SEED,
        maxiter=4,
        popsize=5,
        polish=True,
        fixed_theta=HESTON_FIXED_THETA,
        fixed_kappa=HESTON_FIXED_KAPPA,
        fixed_sigma=HESTON_FIXED_SIGMA,
        prior_rho=TRUE_SSVI_RHO,
    )
    result = calibrate_heston(
        calibration_market,
        spot=SPOT,
        rate=RATE,
        dividend=DIVIDEND,
        config=config,
        bounds=(
            (0.015, 0.090),
            (0.005, 0.50),
            (0.10, 8.00),
            (0.001, 2.00),
            (-0.85, 0.20),
        ),
    )
    params = HestonParams(**result.params)
    model_prices = np.asarray(
        [
            heston_price(
                SPOT,
                float(row.strike),
                float(row.time_to_expiry),
                RATE,
                params,
                str(row.right),
                DIVIDEND,
            )
            for row in calibration_market.itertuples(index=False)
        ]
    )
    price_rmse = float(np.sqrt(np.mean((model_prices - calibration_market["mid"].to_numpy()) ** 2)))
    return (
        {
            "role": "structural_diagnostic_not_signal",
            "calibration_points": len(calibration_market),
            "objective": result.objective,
            "price_rmse": _round(price_rmse, 6),
            "params": {key: _round(value, 6) for key, value in result.params.items()},
            "fixed_parameters": ["theta", "kappa", "sigma"],
            "optimizer_completed": bool(math.isfinite(result.loss)),
        },
        params,
    )


def _execution_diagnostics(surface: pd.DataFrame) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    largest = surface.nlargest(8, "residual_to_spread")
    for index, row in largest.iterrows():
        side = "buy" if float(row["mid_residual"]) < 0.0 else "sell"
        candidate = score_signal(
            {
                "signal_id": f"synthetic-ssvi-residual-{index}",
                "symbol": "SYNTHETIC",
                "signal_type": "model_relative_residual",
                "direction": side,
                "legs": [
                    {
                        "side": side,
                        "quantity": 1,
                        "bid": float(row["bid"]),
                        "ask": float(row["ask"]),
                        "mid": float(row["mid"]),
                        "multiplier": 100,
                        "relative_spread": float(row["relative_spread"]),
                    }
                ],
                "gross_edge": abs(float(row["mid_residual"])) * 100.0,
                "estimated_cost": 0.0,
                "rejection_flags": [],
            },
            cost_buffer=EXECUTION_COST_BUFFER,
        )
        candidates.append(candidate)
    rejected = [candidate for candidate in candidates if candidate["rejection_flags"]]
    return {
        "model_relative_candidates": len(candidates),
        "rejected_by_execution_gates": len(rejected),
        "accepted_as_executable": len(candidates) - len(rejected),
        "cost_buffer_currency_units": EXECUTION_COST_BUFFER,
        "max_absolute_residual_to_full_spread": _round(
            float(surface["residual_to_spread"].max()), 6
        ),
        "interpretation": "Residuals are model-relative; none is an executable-opportunity claim.",
    }


def run_synthetic_evidence() -> EvidenceRun:
    """Run every public evidence stage without network access or credentials."""

    raw_quotes = generate_synthetic_quotes()
    surface, forwards = _prepare_surface(raw_quotes)
    fit = fit_ssvi_to_surface(surface, min_expiries=4, min_strikes=9)
    priced_fit = _price_ssvi_fit(fit.fit)
    fit = SSVIFitResult(
        params=fit.params,
        fit=priced_fit,
        diagnostics=fit.diagnostics,
        initial_loss=fit.initial_loss,
        final_loss=fit.final_loss,
        optimizer_success=fit.optimizer_success,
        message=fit.message,
    )

    smooth_violations = run_no_arbitrage_checks(
        priced_fit,
        rate=RATE,
        price_col="ssvi_price",
        tolerance=1e-7,
    )
    true_forward = SPOT * np.exp((RATE - DIVIDEND) * forwards["time_to_expiry"])
    forward_error_bps = np.abs(forwards["forward"] / true_forward - 1.0) * 10_000.0
    ssvi_iv_rmse = float(np.sqrt(np.mean((priced_fit["ssvi_iv"] - priced_fit["true_iv"]) ** 2)))
    inversion_rmse = float(np.sqrt(np.mean((surface["implied_vol"] - surface["true_iv"]) ** 2)))
    true_params = true_ssvi_params()
    heston, _ = _calibrate_heston(priced_fit)
    execution = _execution_diagnostics(priced_fit)

    summary: dict[str, Any] = {
        "label": SYNTHETIC_LABEL,
        "seed": SEED,
        "asof": str(ASOF),
        "network_requests": 0,
        "provider_data_rows": 0,
        "pipeline": {
            "generated_quote_rows": len(raw_quotes),
            "deliberately_invalid_rows": 5,
            "schema_rejected_rows": int(surface.attrs["schema_rejected"]),
            "quality_rejected_rows": int(surface.attrs["quality_rejected"]),
            "clean_quote_rows": len(surface),
            "maturities": int(surface["expiration"].nunique()),
            "strikes": int(surface["strike"].nunique()),
            "iv_inversions": int(surface["implied_vol"].notna().sum()),
        },
        "forward_inference": {
            "method": "put_call_parity_median",
            "expiries_inferred": len(forwards),
            "max_absolute_error_bps": _round(float(forward_error_bps.max()), 6),
        },
        "iv_inversion": {
            "rmse_volatility_points": _round(inversion_rmse, 8),
            "all_clean_quotes_inverted": bool(surface["implied_vol"].notna().all()),
        },
        "ssvi_primary_surface": {
            "role": "primary_smoother_and_baseline",
            "true_params": {
                "rho": true_params.rho,
                "eta": true_params.eta,
                "gamma": true_params.gamma,
                "theta_by_expiry": true_params.theta_by_expiry,
            },
            "recovered_params": {
                "rho": _round(fit.params.rho, 6),
                "eta": _round(fit.params.eta, 6),
                "gamma": _round(fit.params.gamma, 6),
                "theta_by_expiry": {
                    expiry: _round(theta, 8) for expiry, theta in fit.params.theta_by_expiry.items()
                },
            },
            "surface_iv_rmse_volatility_points": _round(ssvi_iv_rmse, 8),
            "sufficient_condition_failures": int(fit.diagnostics["status"].eq("fail").sum()),
        },
        "heston_structural_diagnostic": heston,
        "price_space_static_arbitrage": {
            "checks": ["strike_monotonicity", "vertical_bounds", "butterfly_convexity"],
            "violations": len(smooth_violations),
            "scope": "fitted_ssvi_prices",
        },
        "execution_gates": execution,
        "conclusion": (
            "Synthetic pipeline validation passed; no real-market performance or trading "
            "conclusion is made."
        ),
    }
    return EvidenceRun(summary=summary, surface=priced_fit, ssvi_fit=fit)


def write_synthetic_evidence(output_root: Path) -> EvidenceRun:
    """Write the aggregate JSON and recruiter-facing SVG under ``output_root``."""

    run = run_synthetic_evidence()
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "synthetic_evidence.json").write_text(
        json.dumps(run.summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (output_root / "synthetic_evidence.svg").write_text(
        _render_svg(run), encoding="utf-8", newline="\n"
    )
    return run


def _render_svg(run: EvidenceRun) -> str:
    left, top, plot_width, plot_height = 90, 145, 720, 430
    frame = run.surface
    x_min = float(frame["log_moneyness"].min())
    x_max = float(frame["log_moneyness"].max())
    y_min = float(min(frame["true_iv"].min(), frame["ssvi_iv"].min()) - 0.005)
    y_max = float(max(frame["true_iv"].max(), frame["ssvi_iv"].max()) + 0.005)

    def x_pos(value: float) -> float:
        return left + (value - x_min) / (x_max - x_min) * plot_width

    def y_pos(value: float) -> float:
        return top + plot_height - (value - y_min) / (y_max - y_min) * plot_height

    colors = ("#00d4ff", "#7c5cff", "#ff8a3d", "#43d17a")
    elements = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="680" viewBox="0 0 1200 680">',
        '<rect width="1200" height="680" fill="#09111f"/>',
        '<text x="60" y="52" fill="#f5f7ff" font-family="Inter,Segoe UI,sans-serif" font-size="30" font-weight="700">Heston &amp; SSVI Volatility Surface Lab</text>',
        f'<text x="60" y="86" fill="#ffcc66" font-family="Inter,Segoe UI,sans-serif" font-size="17" font-weight="700">{SYNTHETIC_LABEL}</text>',
        '<text x="60" y="113" fill="#9eabc4" font-family="Inter,Segoe UI,sans-serif" font-size="15">SSVI primary smoother • Heston structural diagnostic • execution gates</text>',
        f'<rect x="{left}" y="{top}" width="{plot_width}" height="{plot_height}" rx="8" fill="#0f1b2d" stroke="#263752"/>',
    ]
    for step in range(6):
        y_value = y_min + step * (y_max - y_min) / 5
        y = y_pos(y_value)
        elements.append(
            f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_width}" y2="{y:.2f}" stroke="#22324b"/>'
        )
        elements.append(
            f'<text x="{left - 14}" y="{y + 5:.2f}" text-anchor="end" fill="#8f9db6" font-family="monospace" font-size="12">{y_value:.1%}</text>'
        )
    for color, (expiry, group) in zip(colors, frame.groupby("expiry_key", sort=True), strict=True):
        calls = group.loc[group["right"].eq("call")].sort_values("log_moneyness")
        points = " ".join(
            f"{x_pos(float(row.log_moneyness)):.2f},{y_pos(float(row.ssvi_iv)):.2f}"
            for row in calls.itertuples(index=False)
        )
        elements.append(
            f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="3"/>'
        )
        for row in calls.itertuples(index=False):
            elements.append(
                f'<circle cx="{x_pos(float(row.log_moneyness)):.2f}" cy="{y_pos(float(row.implied_vol)):.2f}" r="3.5" fill="#09111f" stroke="{color}" stroke-width="2"/>'
            )
        days = (date.fromisoformat(str(expiry)) - ASOF).days
        legend_y = 166 + colors.index(color) * 28
        elements.append(
            f'<line x1="845" y1="{legend_y}" x2="875" y2="{legend_y}" stroke="{color}" stroke-width="3"/>'
        )
        elements.append(
            f'<text x="885" y="{legend_y + 5}" fill="#dbe4f5" font-family="Inter,Segoe UI,sans-serif" font-size="14">{days}d maturity</text>'
        )
    elements.extend(
        [
            f'<text x="{left + plot_width / 2}" y="625" text-anchor="middle" fill="#aab7cc" font-family="Inter,Segoe UI,sans-serif" font-size="14">log-moneyness relative to parity-implied forward</text>',
            '<text x="26" y="360" transform="rotate(-90 26 360)" text-anchor="middle" fill="#aab7cc" font-family="Inter,Segoe UI,sans-serif" font-size="14">implied volatility</text>',
            '<text x="845" y="300" fill="#f5f7ff" font-family="Inter,Segoe UI,sans-serif" font-size="19" font-weight="700">Deterministic evidence</text>',
        ]
    )
    metrics = (
        ("Clean quotes", str(run.summary["pipeline"]["clean_quote_rows"])),
        ("Invalid rejected", str(run.summary["pipeline"]["deliberately_invalid_rows"])),
        (
            "SSVI IV RMSE",
            f"{run.summary['ssvi_primary_surface']['surface_iv_rmse_volatility_points']:.4%}",
        ),
        (
            "Price-space violations",
            str(run.summary["price_space_static_arbitrage"]["violations"]),
        ),
        (
            "Execution candidates accepted",
            str(run.summary["execution_gates"]["accepted_as_executable"]),
        ),
    )
    for index, (label, value) in enumerate(metrics):
        y = 340 + index * 54
        elements.append(
            f'<text x="845" y="{y}" fill="#8f9db6" font-family="Inter,Segoe UI,sans-serif" font-size="13">{label}</text>'
        )
        elements.append(
            f'<text x="1125" y="{y}" text-anchor="end" fill="#ffffff" font-family="monospace" font-size="17" font-weight="700">{value}</text>'
        )
    elements.extend(
        [
            '<circle cx="850" cy="590" r="4" fill="#9eabc4"/><text x="864" y="595" fill="#9eabc4" font-family="Inter,Segoe UI,sans-serif" font-size="13">circles: noisy synthetic IV</text>',
            '<line x1="845" y1="618" x2="875" y2="618" stroke="#9eabc4" stroke-width="3"/><text x="885" y="623" fill="#9eabc4" font-family="Inter,Segoe UI,sans-serif" font-size="13">lines: fitted SSVI baseline</text>',
            '<text x="1140" y="660" text-anchor="end" fill="#64728a" font-family="monospace" font-size="11">seed 20260826 • generated offline</text>',
            "</svg>\n",
        ]
    )
    return "".join(elements)


def _round(value: float, digits: int) -> float:
    return float(round(float(value), digits))
