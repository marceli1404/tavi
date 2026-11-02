# Tavi v0.21: reuse control-resolver startup

For repeated exact control lookups, `python tavi.py target-controls-stream` accepts JSON lines and keeps the process running. Every request supplies a full observation and queries; the server retains no previous observation. Exact identity, state, geometry, freshness and ambiguity checks remain.

The stream never captures UI, calls hosted models, authorizes or clicks. Results retain null probability and require live supported-host verification. No screenshot-model qualification, accepted weights or routing changes are included.

Read [the protocol and measured limits](Features-control-stream.md). Run `python benchmark_control_stream.py` from a clean checkout to reproduce the synthetic CLI comparison; existing evidence directories are preserved. Twelve paired trials measured158.881ms one-shot versus0.248ms warm requests, with142.354ms startup separately. These are resolver command timings, excluding UI acquisition, agent review, live checks, clicks and app response. No whole-agent speed claim follows.

Validation: the private development suite passed394tests. 281 public source tests pass9.726s. Clean archive checks are performed separately before publication. Five added tests cover parity, no authorization, fresh/stale/future states, ambiguity, missing observations, rejected options, malformed requests, bounded frames and recovery. Native CLI benchmark responses matched after excluding elapsed age. Native Unix execution has not been tested. Research candidates and operator records are excluded.
