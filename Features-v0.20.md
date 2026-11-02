# Tavi v0.20: explicit feedback for screen-target observations

Tavi can now save explicit local assessments of a supplied target proposal and summarize them by model and feature schema. Target correctness and action outcome have separate counts. Unknown and conflicting assessments remain visible; repeated observations and copied event files do not inflate denominators.

```sh
python tavi.py target-feedback proposal.json observation.json
python tavi.py target-feedback-summary data/target-feedback
```

Read [the observation format and neutral template](Features-target-feedback.md) before recording. An observation must name the same proposal and candidate as the supplied proposal. New proposals include a uniform target-model weights hash and feature schema. Older proposals lacking that fingerprint are rejected rather than assigned a guessed model.

Recording is off by default. These commands do not capture screens, run OCR, call a hosted model, click, train weights or change action qualification. They work without routing configuration or model inventory. Events retain source hashes and explicit operator evidence, without automatically copying screenshot pixels, raw task text, target labels or nearby OCR text. Evidence text is supplied and retained explicitly by the operator.

Summaries report raw score bins, model/schema separation, unique image hashes and image-task bindings alongside distinct observations. These counts do not establish independent trials or representative field performance. Operator-entered assessments are not authenticated host facts or calibrated action-success probabilities. A recorded rate of100% is not a guarantee; qualification remains false.

The existing95% pixel-action guard is unchanged. Accepted router and target weights, selected routes, thresholds, live-host checks and click permissions are unchanged. Rejected private research candidates and operator records are excluded from the package.

## Validation

The local development suite passes381tests. 276 public source tests pass. The clean archive is verified separately before release. Checks cover exact proposal/candidate binding, finite unrounded scores, model/schema separation, duplicate/conflict handling, distinct target/action outcomes, privacy of retained fields, bounded inputs, offline CLI use, real synthetic-proposal integration and existing action guards.

The CLI smoke check uses contradictory assessments of a saved synthetic fixture. It verifies append-preserving records, one conflicted observation, an unknown match rate and no known action result. It collects no real field outcome or calibration evidence. No live Claude sign-in was used.
