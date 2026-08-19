"""Small conservative option backtest engine."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pandas as pd

from heston_arb_lab.backtest.costs import CostConfig, slippage_cost
from heston_arb_lab.backtest.execution import option_exit_price, option_fill_price


def round_trip_option_pnl(
    *,
    side: str,
    quantity: float,
    entry_bid: float,
    entry_ask: float,
    exit_bid: float,
    exit_ask: float,
    cost_config: CostConfig | None = None,
) -> dict[str, float]:
    """Compute a conservative single-option round-trip PnL."""

    cfg = cost_config or CostConfig()
    entry = option_fill_price(side, entry_bid, entry_ask)
    exit_price = option_exit_price(side, exit_bid, exit_ask)
    signed = 1.0 if side.lower() == "buy" else -1.0
    gross = signed * (exit_price - entry) * quantity * cfg.option_multiplier
    fees = 2.0 * cfg.option_fee_per_contract * abs(quantity)
    slippage = slippage_cost(
        entry, quantity, cfg.option_multiplier, cfg.slippage_bps
    ) + slippage_cost(exit_price, quantity, cfg.option_multiplier, cfg.slippage_bps)
    return {
        "entry_price": entry,
        "exit_price": exit_price,
        "gross_pnl": gross,
        "fees": fees,
        "slippage": slippage,
        "net_pnl": gross - fees - slippage,
    }


def backtest_static_signals(
    signals: Iterable[dict[str, Any]],
    *,
    exit_mid_multiplier: float = 1.05,
    cost_config: CostConfig | None = None,
) -> pd.DataFrame:
    """Toy static backtest that exits each first leg with a deterministic mark move."""

    rows: list[dict[str, Any]] = []
    for signal in signals:
        legs = signal.get("legs", [])
        if not legs:
            continue
        leg = legs[0]
        side = str(leg.get("side", "buy"))
        bid = float(leg.get("bid", leg.get("mid", 0.0)))
        ask = float(leg.get("ask", leg.get("mid", bid)))
        mid = float(leg.get("mid", (bid + ask) / 2.0))
        exit_mid = mid * exit_mid_multiplier if side == "buy" else mid / exit_mid_multiplier
        half_spread = max(ask - bid, 0.0) / 2.0
        result = round_trip_option_pnl(
            side=side,
            quantity=float(leg.get("quantity", 1.0)),
            entry_bid=bid,
            entry_ask=ask,
            exit_bid=max(exit_mid - half_spread, 0.0),
            exit_ask=exit_mid + half_spread,
            cost_config=cost_config,
        )
        rows.append(
            {"signal_id": signal.get("signal_id"), "symbol": signal.get("symbol"), **result}
        )
    return pd.DataFrame(rows)
