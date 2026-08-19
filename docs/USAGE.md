# CLI and API usage

Run the network-free demonstration:

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
from heston_arb_lab.surface.surface_builder import synthetic_option_chain
```

The artificial-chain helper is intended for examples and tests. Users are responsible for
validating any locally supplied data before interpreting diagnostics.
