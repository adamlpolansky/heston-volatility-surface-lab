# CLI and API usage

Regenerate the committed, network-free evidence pack:

```bash
python -m heston_arb_lab.cli synthetic-evidence
```

Run the same pipeline in memory without writing artifacts:

```bash
python -m heston_arb_lab.cli demo
```

Inspect the environment without contacting a provider:

```bash
python -m heston_arb_lab.cli doctor
python -m heston_arb_lab.cli provider-status
```

The Python API exposes numerical modules directly, for example:

```python
from heston_arb_lab.models.black_scholes import bs_price, implied_volatility
from heston_arb_lab.models.heston_cf import HestonParams
from heston_arb_lab.models.ssvi import SSVIParams
from heston_arb_lab.synthetic_evidence import run_synthetic_evidence
```

The evidence API returns aggregate results and an in-memory synthetic surface. It does not load
or persist market data. Users are responsible for validating any separately supplied local data
before interpreting diagnostics.
