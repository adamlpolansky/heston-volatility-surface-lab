"""Conservative bid/ask execution rules."""

from __future__ import annotations


def option_fill_price(side: str, bid: float, ask: float) -> float:
    """Buy at ask, sell at bid."""

    lowered = side.lower()
    if lowered == "buy":
        return ask
    if lowered == "sell":
        return bid
    raise ValueError("side must be buy or sell")


def option_exit_price(entry_side: str, bid: float, ask: float) -> float:
    """Exit a long at bid and a short at ask."""

    lowered = entry_side.lower()
    if lowered == "buy":
        return bid
    if lowered == "sell":
        return ask
    raise ValueError("entry_side must be buy or sell")
