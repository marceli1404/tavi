# Tavi v0.19: quicker cached observations and clearer routing explanations

Exact-input screenshot cache hits now return before image decoding, resizing and PNG encoding. The cache key binds the complete original image bytes and the task, target, mode, model, reasoning effort, policy, schema and image limit. Cache misses prepare the same captured bytes used for that identity. Original geometry and EXIF remain part of the source-byte identity.

Expiry, future timestamps, malformed entries and changed settings still cause a cache miss. Cached responses are validated and coordinate mappings rebuilt from the stored analysis. Unexecuted hosted plans remain uncached. Version1 entries are ignored by the new version2 key; they need not be deleted.

A cached observation does not establish current live state or permission to act. Tavi still provides no input backend; the host must verify the intended control before acting. Pixel probability qualification remains false.

## Measured cache path

A paired alternating benchmark used three saved synthetic1200x700 fixtures,60 warm pairs and15 cold pairs. Both implementations used the same native Windows OCR callback to initialize separate caches; no hosted requests were sent. All compared observation outputs matched.

| Path | Previous median | v0.19 median |
|---|---:|---:|
|Exact-input warm cache hit|32.263ms|0.946ms|
|Cold preparation with identical OCR stub|30.583ms|30.988ms|

The warm cache path was34.09x faster in this small local measurement. Capture, live-state verification, agent reasoning, clicks, hosted inference and interpreter startup are excluded. This is not34x faster complete computer use, nor a field-accuracy result. Cache hits still read and hash the full source bytes.

Evidence, source and synthetic fixtures are in `benchmarks/vision-cache-v0.19`. Reproduce a new offline cache benchmark with optional vision dependencies installed:

```sh
python benchmarks/vision_cache.py output/cache-speed-replay
```

An existing output folder is preserved. Native OCR is Windows-only; timings vary by machine and workload.

## Routing evidence

Routes now include `routing_evidence` describing the predicted tier, vocabulary coverage, thresholds, model availability and reasons a plan was withheld. Warnings distinguish these causes. A classifier prediction of review alone does not establish that the user's task is ambiguous or missing information.

This reporting-only change preserves chosen models, skills, routes, launch plans, thresholds and action gates. Scores remain authored-policy scores, not task-success probabilities. Rejected experimental models and private project data are excluded from this release. Claude support remains available; live Claude testing remains deferred by the owner.

## Package validation

262 public source tests pass. A fresh public-checkout benchmark replay preserved all60 paired warm outputs and measured30.72ms versus0.93ms; this repeat is the same small synthetic workload, not independent field evidence. The package uses an explicit file allowlist and per-file SHA256 manifest. Accepted router and target weights are unchanged.
