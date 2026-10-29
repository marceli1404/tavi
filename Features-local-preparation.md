# Faster local screenshot preparation (v0.17)

Two CPU changes reduce work in local target proposals:

- Keep the decoded RGB bitmap in byte form and convert only the sampled background, word and border regions to floating point. Preserve the previous strided mean reduction so existing features keep their rounding behavior.
- Encode temporary local-OCR PNGs with fast lossless compression. The general vision path and proposals permitting image fallback retain compact PNG encoding, avoiding larger image uploads. Decoded pixels, scaling and pixel hashes are unchanged.

## Matched results

Thirty order-balanced triplets reuse the exact screenshot/task/target/box inputs from the earlier field benchmark. There are12positive button requests. Each method occurs in each sequence position10times; no target or timing-score selection is used.

| Method | Median local preparation |
|---|---:|
| v0.16, fresh OCR process | 568.1ms |
| v0.16, warm OCR session | 141.8ms |
| Optimized warm session | 89.6ms |

That is36.8% less time than the prior warm pipeline (1.58x ratio of medians), or6.34x relative to fresh-process preparation in this test. Timing includes source hashing, image preparation/encoding, OCR, candidate scoring and qualification planning. It excludes interpreter startup, host capture, agent review, physical input, UI response and hosted inference. It is not a6x whole-agent/computer-use claim. First use still pays worker initialization and initial OCR; these are warm-session medians.

The feature-only test has240measurements per method over48requests:12.19ms to3.62ms median (3.36x). One large-frame tracemalloc check drops from55.30MB to0.58MB tracked peak; native Pillow bitmap allocations are excluded, so this is not total application memory.

## Correctness and limitations

Across24saved browser screenshots, all670unique recorded task/target requests and1225candidates retain exactly equal features, scores and rankings. The30matched complete proposals have equal targets, confidence and review reasons; proposal IDs remain fresh. Every method identifies the correct target in only5/12positive requests. Automatic qualification remains false, zero candidates qualify, and no hosted call or input action occurs. Faster computation does not fix recognition accuracy or establish live UI state.

Six added tests cover RGB/RGBA/grayscale and reduction-rounding compatibility, invalid geometry, bounded sampled float areas, pixel/geometry/hash identity between PNG encodings, retained compact encoding for image fallback and invalid compression values. All271development software tests pass. A real two-request propose-stream smoke check confirms one owned OCR worker, request counts1/2, distinct proposal IDs, no proposal reuse and no hosted calls or automatic candidates.

The first feature benchmark caught a5.55e-17 roundoff difference. That failed experiment is retained; preserving the strided ink reduction resolved it. The first patch-only proposal test showed no overall gain, which motivated the PNG change. The initial30-case SHA-ranked run had only two positive targets; the final comparison uses the original benchmark's12positive cases instead.

Historical dataset-wide metadata hashes differ. The replay explicitly verifies every used screenshot hash and all30frozen target boxes against the current records, then takes task/target/box inputs verbatim from the historical manifest. Unrelated metadata is not used for inference. Both hashes and this verification are recorded; no accuracy or probability gate was lowered.

Published summaries and sanitized timing rows are in benchmarks/local-preparation-v0.17/evidence.json. The source screenshot corpus is local and is not included. Accepted routing/target weights and action policy are unchanged.
