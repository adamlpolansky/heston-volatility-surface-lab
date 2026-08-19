# Data contracts

Canonical schemas are defined in `heston_arb_lab.data.schemas` and validated before numerical
work begins. Important fields include symbol, timestamp, expiration, strike, option right, bid,
ask, sizes, and underlying price.

Validation is deliberately conservative:

- timestamps are normalized before alignment;
- malformed or crossed quotes are rejected or flagged;
- bid/ask width and staleness can be bounded;
- option rights are normalized explicitly;
- numerical routines require finite, positive inputs where their mathematics requires them.

Provider-specific column names are translated only inside narrow adapters. Downstream modules
operate on canonical frames and do not depend on a provider response format.
