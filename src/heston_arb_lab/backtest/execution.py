"""Conservative bid/ask execution rules."""

from __future__ import annotations


def validate_trade_side(side: object) -> str:
    """Return a normalized side and fail closed for missing or unknown values."""

    if not isinstance(side, str):
        raise ValueError("side must be an explicit 'buy' or 'sell' string")
    lowered = side.lower()
    if lowered not in {"buy", "sell"}:
        raise ValueError("side must be buy or sell")
    return lowered


def option_fill_price(side: str, bid: float, ask: float) -> float:
    """Buy at ask, sell at bid."""

    lowered = validate_trade_side(side)
    if lowered == "buy":
        return ask
    if lowered == "sell":
        return bid
    raise AssertionError("validated trade side was not handled")


def option_exit_price(entry_side: str, bid: float, ask: float) -> float:
    """Exit a long at bid and a short at ask."""

    lowered = validate_trade_side(entry_side)
    if lowered == "buy":
        return bid
    if lowered == "sell":
        return ask
    raise AssertionError("validated trade side was not handled")
