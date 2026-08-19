"""Typed internal data contracts."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Right = Literal["call", "put"]
Side = Literal["buy", "sell"]

OPTION_QUOTE_COLUMNS = [
    "symbol",
    "expiration",
    "strike",
    "right",
    "timestamp",
    "bid",
    "ask",
    "bid_size",
    "ask_size",
]

UNDERLYING_BAR_COLUMNS = [
    "symbol",
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "adj_close",
]


class OptionContract(BaseModel):
    """Listed option contract identity."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    expiration: date
    strike: float = Field(gt=0)
    right: Right


class OptionQuote(OptionContract):
    """Normalized NBBO option quote."""

    timestamp: datetime
    bid: float = Field(ge=0)
    ask: float = Field(ge=0)
    bid_size: int = Field(default=0, ge=0)
    ask_size: int = Field(default=0, ge=0)


class UnderlyingBar(BaseModel):
    """Normalized OHLCV bar."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    adj_close: float | None = None


class SurfacePoint(OptionQuote):
    """Cleaned option quote enriched with surface features."""

    mid: float
    spread: float
    time_to_expiry: float
    implied_vol: float
    log_moneyness: float
    total_variance: float


class CalibrationResult(BaseModel):
    """Serializable Heston calibration output."""

    model_config = ConfigDict(extra="allow")

    params: dict[str, float]
    loss: float
    objective: str
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class SignalCandidate(BaseModel):
    """A candidate arbitrage or model-relative signal."""

    model_config = ConfigDict(extra="allow")

    signal_id: str
    symbol: str
    asof: datetime
    signal_type: str
    legs: list[dict[str, Any]]
    gross_edge: float
    estimated_cost: float
    net_edge: float
    confidence: float
    rejection_flags: list[str] = Field(default_factory=list)


class BacktestTrade(BaseModel):
    """Executed trade used by the conservative backtest engine."""

    model_config = ConfigDict(extra="allow")

    trade_id: str
    timestamp: datetime
    symbol: str
    instrument: str
    quantity: float
    side: Side
    price: float
    fees: float = 0.0
    slippage: float = 0.0
