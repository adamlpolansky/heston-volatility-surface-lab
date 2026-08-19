"""Backtest metrics."""

from __future__ import annotations

import math

import pandas as pd


def compute_metrics(trades: pd.DataFrame) -> dict[str, float]:
    """Compute compact performance metrics from trade-level PnL."""

    if trades.empty:
        return {
            "gross_pnl": 0.0,
            "net_pnl": 0.0,
            "drawdown": 0.0,
            "hit_rate": 0.0,
            "turnover": 0.0,
            "sharpe": math.nan,
        }
    pnl = trades["net_pnl"].astype(float)
    equity = pnl.cumsum()
    drawdown = (equity.cummax() - equity).max()
    std = pnl.std(ddof=1)
    sharpe = float(pnl.mean() / std * math.sqrt(len(pnl))) if len(pnl) > 2 and std > 0 else math.nan
    return {
        "gross_pnl": float(trades["gross_pnl"].sum()),
        "net_pnl": float(pnl.sum()),
        "drawdown": float(drawdown),
        "hit_rate": float((pnl > 0).mean()),
        "turnover": float(len(trades)),
        "average_spread_paid": float((trades["fees"] + trades["slippage"]).mean()),
        "sharpe": sharpe,
    }
