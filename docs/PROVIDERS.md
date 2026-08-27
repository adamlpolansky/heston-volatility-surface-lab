# Optional provider boundary

The public project neither requires nor exercises a market-data provider. ThetaData support is
retained only as an optional code interface and defaults to `dry_run=True`. It contains no
credential, response cache or embedded provider output.

The public demo and CI must not instantiate a live client or perform a provider request. The
default installation therefore excludes the provider extra. The only provider-derived materials
in the repository are the exact frozen aggregate artifacts in the approved case-study directory;
they are not inputs to the software, tests or CI.

Possession of this source code grants no provider access or data rights. The case-study permission
is personal, non-commercial and non-transferable, and it does not authorize third-party
redistribution or sublicensing. Any other activation or publication requires separate written
authorization and a new publication-boundary review. See the
[public-data policy](PUBLIC_DATA_POLICY.md).
