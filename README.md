# Heston & SSVI Volatility Surface Lab

End-to-end options-surface research framework covering quote validation, option-implied
forwards, IV inference, SSVI smoothing, Heston calibration and execution-aware arbitrage
diagnostics.

![SYNTHETIC evidence: fitted SSVI surface and pipeline diagnostics](docs/assets/synthetic_evidence.svg)

```bash
python -m heston_arb_lab.cli synthetic-evidence
```

| Deterministic result (seed `20260826`) | SYNTHETIC evidence |
|---|---:|
| Generated / clean quote rows | 77 / 72 |
| Deliberately invalid rows rejected | 5 / 5 |
| Parity-implied forwards | 4 expiries; 0.000000 bps max error (expected by construction: the shared call/put midpoint perturbation cancels in `C - P`) |
| Robust IV inversions | 72 / 72; 0.00005146 RMSE |
| Primary SSVI surface recovery | 0.00010862 IV RMSE; 0 condition failures |
| Heston structural calibration | 12 points; 0.245983 price RMSE |
| Fitted-price static-arbitrage flags | 0 |
| Residual candidates rejected by execution gates | 8 / 8; 0 accepted |

The `0.000000 bps` forward error is a pipeline invariant: each matched call and put receives
the same synthetic midpoint perturbation, which cancels exactly in `C - P`. It validates the
parity-forward implementation; it is not a claim of statistical estimation accuracy on noisy
market data.

> **SYNTHETIC ONLY. No market-data evidence, provider-derived output, empirical performance,
> mispricing, profitability or executable-trading claim is included.**

[![CI](https://github.com/adamlpolansky/heston-volatility-surface-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/adamlpolansky/heston-volatility-surface-lab/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](pyproject.toml)

## What this demonstrates

The fixed-seed evidence pack runs one synthetic chain through the complete publication path:

1. strict row-schema validation and quote-quality rejection;
2. forward inference from matched calls and puts using put-call parity;
3. bounded Black–Scholes implied-volatility inversion;
4. SSVI fitting and recovery against known synthetic surface parameters;
5. reduced Heston calibration as a structural diagnostic;
6. strike, vertical-spread and butterfly checks on fitted prices;
7. model-residual-to-bid/ask-spread measurement; and
8. fees, spread cost and cost-buffer rejection gates.

SSVI is the **primary surface smoother and baseline**. Heston is an independently specified
**structural diagnostic model**. Neither model is an automatic trading signal.

The generator uses four maturities, nine strikes, both option rights, controlled fixed-seed
midpoint noise and observable bid/ask spreads. It appends five deliberately invalid rows: a
crossed market, a negative bid, a missing ask, an unknown option right and a negative strike.
Only aggregate evidence is committed; quote rows are never written.

## Three different claims

- A **model-relative residual** is the difference between a quote midpoint and a fitted-model
  price. It can be ordinary model error and is not an arbitrage statement.
- A **static-arbitrage flag** is a failed mathematical price constraint under the diagnostic's
  assumptions. It remains a screening result, not proof of a fillable trade.
- An **executable opportunity** would additionally survive contemporaneous bid/ask prices,
  realistic fills, fees, slippage, financing, borrow, exercise, latency and operational risk.
  This repository reports none.

## Reproduce offline

Use Python 3.12. The default installation excludes all provider clients.

```bash
python -m venv .venv
python -m pip install -c constraints/py312.txt -e ".[dev]"
python -m pip check
python -m heston_arb_lab.cli synthetic-evidence
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m mypy src
```

The regeneration command rewrites only the labelled aggregate
[`synthetic_evidence.json`](docs/assets/synthetic_evidence.json) and
[`synthetic_evidence.svg`](docs/assets/synthetic_evidence.svg). CI regenerates them and fails
if bytes differ. The demo, test suite and CI make no provider request and require no credential.

## Public boundary

No ThetaData or other restricted-provider data is used. No private single-name study, quote
row, cached response, fitted real-data parameter, metric, plot, table or conclusion is
published. The optional adapter remains an inert code interface: it is excluded from the
default dependency set, defaults to dry-run behavior, and is not exercised by the public
evidence command.

See the [public-data policy](docs/PUBLIC_DATA_POLICY.md), [methodology](docs/METHODOLOGY.md),
[limitations](docs/LIMITATIONS.md), [architecture](docs/ARCHITECTURE.md), and
[reproducibility guide](docs/REPRODUCIBILITY.md).

## License and author

Original project content is licensed under the [MIT License](LICENSE), copyright 2026
Adam Luboš Polanský. Provider services, client libraries and market data remain subject to
their respective terms and licences; none of their data is distributed here.
