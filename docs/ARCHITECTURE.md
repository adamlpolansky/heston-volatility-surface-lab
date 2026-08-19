# Architecture

The package separates reusable numerical logic from optional data access:

1. `data` defines canonical schemas, quote-quality checks, local storage helpers, and the
   optional provider adapter.
2. `surface` cleans quotes, infers forwards, solves implied volatility, interpolates surfaces,
   and evaluates price-space necessary conditions.
3. `models` implements Black–Scholes, Heston characteristic-function pricing and calibration,
   and SSVI total variance.
4. `signals` transforms model residuals or constraint violations into conservatively scored
   diagnostic candidates.
5. `backtest` supplies generic execution, cost, hedging, and metric components for local use.

Provider packages are optional. Importing and testing the numerical core requires no provider
credential or network connection. The default CLI demo constructs all inputs in memory.
