# Tavi v0.22: compact control batches

Send `"compact": true` to `target-controls-stream` to factor repeated observation fields into `shared_proposal_fields`. Expand each proposal with the shared fields to recover every original result field. The default response format stays the same.

Synthetic responses were 50.8% smaller for ten queries and 58.2% smaller for one hundred. Single-query output was 3.6% larger; use standard output for that case. Compaction adds local encoding work. These are payload measurements, with no measured full-agent speedup or model token-count claim.

Fresh observations, stale/future rejection, ambiguity, task binding and current-host verification still apply. No actions, calibrated target probability, training or accepted model changes are included.

See [protocol, examples and measured limits](Features-control-compact.md). Reproduce the synthetic comparison with `python benchmark_control_compact.py` from a clean checkout. Evidence is in `benchmarks/control-compact-v0.22/`.

Validation: 285 public source tests pass. A fresh archive extraction passes the same 285 tests, offline prediction and the benchmark with no existing output directory. The archive contains only the explicit release allowlist; research candidates and operator records are excluded.
