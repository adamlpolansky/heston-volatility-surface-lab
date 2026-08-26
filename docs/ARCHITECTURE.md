# Architecture

The recruiter-facing path is deliberately small and offline:

```text
fixed-seed SYNTHETIC quotes
  -> schema + quality gates
  -> parity-implied forwards
  -> IV inversion
  -> SSVI primary surface
  -> Heston structural diagnostic
  -> fitted-price static-arbitrage checks
  -> residual/spread execution gates
  -> aggregate JSON + labelled SVG
```

`data` owns canonical schemas and quote-quality checks. `surface` owns forward inference, IV
inversion and price constraints. `models` owns Black–Scholes, SSVI and Heston numerics.
`signals` and `backtest.execution` provide cost-aware diagnostic gating; they do not authorize
or route orders. `synthetic_evidence` composes those modules without importing a provider
adapter.

Provider code is an optional boundary outside this path. The default environment, CLI evidence
command and CI need neither a provider package nor a credential.
