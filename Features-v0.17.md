# Tavi v0.17: faster local screenshot preparation

Local target proposals now convert sampled pixel regions rather than the whole screenshot to floating point, and use fast lossless PNG encoding for local-only OCR. General vision and permitted image uploads keep compact encoding. Decoded pixels and coordinate geometry remain unchanged.

On the original30-case saved-screen workload, median preparation is89.6ms versus141.8ms for v0.16warm sessions:36.8% less time. The matched fresh-process baseline is568.1ms (6.34x ratio). These timings exclude interpreter startup, host capture, agent review, clicks, app response and hosted inference. First use still pays initialization and initial OCR. They are not a6x whole-agent speedup.

All670recorded task/target requests and1225candidates retain exactly equal features, scores and rankings in the comparison. The benchmark still identifies correct targets in only5/12positive requests. No target qualifies for automatic clicks; accepted model weights and qualification policy are unchanged.

Six new tests cover numerical compatibility, sampled allocation, identical lossless pixels/geometry and image-fallback compression policy.234tests pass in stable source and clean extraction. See Features-local-preparation.md and benchmarks/local-preparation-v0.17/evidence.json for measured results and limits. Private screenshots, research models, configuration and project ledgers are excluded.
