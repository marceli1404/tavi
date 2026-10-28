# Tavi v0.9 — Coding coverage and context-scoped calibration

## What changed

A separate residual coding classifier operates only when the request contains an explicit Python function signature and docstring. The original v3 arrays and ordinary-text workload scores remain frozen; skill/external-search outputs are also unchanged. Generic structural features are learned inputs, not hard-coded model choices. The new head uses232 authored code training examples and68 validation examples; epoch500 and confidence gate0.55 use validation only. No public benchmark prompt or outcome label is fitted.

The final artifact is models/tavi-v4-clean. Original v3/v2 copies and all rejected attempts remain available locally. The initial broad retraining attempt was rejected for ordinary-text regression. A later code-only attempt was also rejected after review found workload labels in synthetic helper names. Those identifiers were replaced with neutral hashes, training/calibration rerun, and a regression test added. Earlier preliminary results are not the released evidence.

## Measured coverage

| Check | V3 | V4 |
|---|---:|---:|
| Historical public tasks |7/8|8/8|
| Prior difficult public audit |4/8|6/8|
| New pre-fixed public audit |8/8|8/8|
| Additional audit after final weights froze |8/8|8/8|

No previously covered route was lost. All prior50/40/32/32 synthetic policy scores remain unchanged. Exact array/head preservation covers1917 examples;1585 non-code examples retain exact tier scores. Public coding coverage is not task success or empirical best-model accuracy.

Two pre-fixed new tasks, HumanEval38 and105, received only their selected model completions (sol/medium and luna/low): two hosted requests, both pass upstream tests. V3 and final V4 select the same routes; the exact task/model/effort outputs were reused after neutral-name correction rather than paying for duplicates. No improvement in task success is claimed. The public historical data may be in foundation-model training. Licence, pinned source and saved answers are included.

The new task38 exposed a harness limitation before generation: its upstream tests import random/string and depend on a helper in the prompt. The judge now preserves the prompt namespace, seeds allowed test randomness and keeps random imports forbidden in candidate code. Cache manifests bind the judge source hash. No task was swapped after a failure.

## Confidence that states its limits

264 synthetic calibration cases are split into132 fit and132 check examples. Each split has96 ordinary-text examples and36 Python specifications. The text examples contain four correlated paraphrases per subject, so these are not132 independent field trials. Tier and external-search temperatures are fitted on fitting labels only. Each head/context combination must separately avoid check-set NLL and Brier regression; failed combinations retain raw scores.

| Context | Tier probability | External-search probability |
|---|---|---|
| Ordinary text |Uncalibrated|Synthetic-policy calibrated|
| Python specification |Synthetic-policy calibrated|Uncalibrated|

Accepted code-tier calibration improves NLL1.3679→0.9895 and Brier0.5873→0.5268. Accepted ordinary-text external calibration improves NLL0.2361→0.1969 and Brier0.1811→0.1474. The other combinations worsened their checks and were not applied. Status is partial, and reports carry context, per-head status and evidence.

The code-context tier-label accuracy is only22/36 (61.11%); temperature scaling does not fix wrong labels. A limited-context-validation review flag is therefore included for code requests. These are same-author policy estimates, not probabilities of successful work or proof of the best commercial model. Skill scores remain uncalibrated. Routing thresholds and execution authority are unchanged.

## Reproduce

```text
python train_coding.py --base models/tavi-v3 --corpus training/coverage_corpus-v4-clean.json --output models/NEW_CANDIDATE
python evaluate_coding.py --base models/tavi-v3 --model models/NEW_CANDIDATE
python calibrate_tavi.py --model models/NEW_CANDIDATE --cases training/probability_cases_v4_clean.json --output NEW_REPORT.json --headwise
```

Raw inference remains local CPU-only. There are no new dependencies, GPU use, website edits or GitHub push in this task. ROUTER-9 still awaits a supported desktop bridge.
