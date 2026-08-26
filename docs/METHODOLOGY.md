# Methodology

## Scope

The committed evidence is a deterministic software-validation exercise, not an empirical
market study. It uses seed `20260826`, synthetic as-of date `2040-01-03`, spot 100, four
maturities, nine strikes and both calls and puts.

SSVI is the primary surface smoother and baseline. Heston is a structural diagnostic model.
Neither produces an automatic trading signal.

## Pipeline

1. **Synthetic generation.** Independently selected SSVI parameters define total variance.
   Black–Scholes converts that surface to internally consistent call and put prices. Fixed-seed
   midpoint noise, variable bid/ask widths and sizes are then added. Five malformed rows test a
   crossed market, negative bid, missing ask, unknown right and negative strike.
2. **Validation and cleaning.** Pydantic schemas reject malformed identities and quote fields.
   Quality flags then reject crossed, negative, missing, tiny or excessively wide markets.
3. **Forward inference.** For each expiry, matched midpoints imply
   `F = K + exp(rT) × (C - P)`. The median across strikes is used rather than the known carry
   forward; the known value is retained only to measure synthetic recovery error. Matched calls
   and puts share the same synthetic midpoint perturbation, so it cancels in `C - P`: zero error
   is an expected pipeline check, not a noisy-market accuracy estimate.
4. **IV inversion.** Clean midpoints are inverted with bounded Black–Scholes root finding.
5. **SSVI fit.** A power-law SSVI surface fits total variance across all maturities. Recovery is
   measured against the generator's known surface, and sufficient calendar/butterfly
   conditions are reported.
6. **Heston calibration.** Twelve synthetic call prices calibrate `v0` and `rho`, while
   independently selected `theta`, `kappa` and vol-of-vol remain fixed. This reduced fit is a
   stable structural comparison, not a claim that Heston generated the chain.
7. **Price-space diagnostics.** Strike monotonicity, vertical bounds and discrete butterfly
   convexity are evaluated on Black–Scholes prices reconstructed from the fitted SSVI surface.
8. **Residual and execution gates.** Midpoint-minus-SSVI residuals are divided by the full
   bid/ask spread. The eight largest model-relative residuals are charged half-spread cost,
   per-contract fees and a fixed synthetic cost buffer. Rejected candidates are not trades.

The public JSON contains aggregate counts, parameters and errors only. It contains no quote
rows. The SVG is a labelled visualization of the synthetic observed IV points and fitted SSVI
curves.
