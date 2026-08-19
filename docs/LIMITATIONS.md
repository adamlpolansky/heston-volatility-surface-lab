# Limitations and non-claims

- Heston and SSVI are modeling choices, not complete descriptions of an option market.
- Numerical calibration can be non-identifiable and sensitive to bounds, weights, initial
  values, data quality, and optimizer behavior.
- Price-space constraints are necessary-condition screens. Input errors, timestamp mismatch,
  American exercise, discrete dividends, borrow, settlement, and contract conventions can
  explain apparent violations.
- Bid/ask and cost filters remain approximations unless validated against contemporaneous,
  executable market access.
- Generic backtesting components do not establish capacity, causality, profitability, or live
  executability.
- Optional provider behavior can change upstream. Users must verify the installed client and
  provider documentation before live access.

The project screens potential static-arbitrage violations. It does not promise guaranteed
arbitrage, profitable opportunities, or investment performance.
