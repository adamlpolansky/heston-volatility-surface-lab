# Limitations and non-claims

- The reproducible software-validation evidence is synthetic and validates implementation
  behavior only. The separately isolated real-data case study contains only permissioned frozen
  aggregates and does not expose or reproduce its underlying market observations.
- Heston and SSVI are modeling choices, not complete descriptions of an option market.
- SSVI is used as the primary smoother; its sufficient conditions and discrete checks are not a
  universal proof of arbitrage freedom under every interpolation or extrapolation.
- Numerical calibration can be non-identifiable and sensitive to bounds, weights, initial
  values, data quality, and optimizer behavior.
- The evidence uses a reduced Heston calibration with three fixed parameters. Its reported
  error is a structural diagnostic on synthetic prices, not model validation on market data.
- Price-space constraints are necessary-condition screens. Input errors, timestamp mismatch,
  American exercise, discrete dividends, borrow, settlement, and contract conventions can
  explain apparent violations.
- Bid/ask and cost filters remain approximations unless validated against contemporaneous,
  executable market access.
- A model-relative residual can arise from smoothing error, numerical error or model mismatch.
  It is not a static-arbitrage violation or an instruction to trade.

The project makes no claim of mispricing, executable arbitrage, profitability or investment
performance. It is research software, not investment advice.
