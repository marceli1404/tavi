# Tavi — consented real-world evidence and safe offline training

**Implemented 3 November 2026 on the development branch; not yet merged.**

This capability closes three measurement/training plumbing gaps **without** claiming that a new computer-use model has been trained or that Tavi can operate arbitrary websites autonomously.

## 1. Real token accounting instead of token guesses

`tavi_provider_usage.py` reads **only** the documented `usage` object from:
- [OpenAI Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create): `input_tokens`, `output_tokens`, `input_tokens_details.cached_tokens`.
- [OpenAI Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create): `prompt_tokens`, `completion_tokens`, `prompt_tokens_details.cached_tokens`.

It never uploads anything or retains a model response body.

```python
from tavi_metrics import UsageMetrics
from tavi_provider_usage import record

metrics = UsageMetrics()
# response comes from a host-owned, properly authorized SDK call
record(metrics, "openai_responses", response, elapsed_ms=host_measured_ms)
report = metrics.summary()
```

Absent or incomplete `usage` stays **unmeasured**. Missing cache data remains **null**, not silently zero. Actual cost comparisons require matched baseline/optimized calls with both reported token counts; no assumption that smaller JSON means fewer billed tokens is allowed. Streaming responses must provide their **final** usage event to count as measured.

## 2. Operator-consented, non-sensitive real-task evidence

`tavi_field_data.py` accepts a **host-provided observation and later verified task result**. It does not browse, capture screenshots, click or infer that an action succeeded. The trusted host must have authorization to perform its task and separately verify the action/result.

Before collecting evidence, the operator must:
1. Explicitly opt in to local collection for the task and confirm the site permits testing.
2. Check that the task/page is **not sensitive**; decline passwords, payment flows, private messages, medical data, account recovery, personal identifiers and other sensitive contexts.
3. Give the collector a private **32+ byte HMAC key** kept out of the data directory and a stable per-site family and task/trial key. Use the same private key when comparing baseline and optimized runs; never put raw URLs or the HMAC key in the checked-in repository.

Example integration:

```python
import os
import time
from tavi_browser_snapshot import capture_controls
from tavi_observe import dispatch
from tavi_field_data import record

key = bytes.fromhex(os.environ["TAVI_EVIDENCE_HMAC_KEY_HEX"])
start = time.perf_counter()

snapshot = capture_controls(page)  # trusted browser host's current Page
packet = dispatch(snapshot, [{
    "id": "probe", "task": "Inspect submit control",
    "target": "Submit", "role": "button"
}])

# Your separately authorized host/user now handles any requested action
# and independently verifies the result. Tavi DOES NOT execute the action.
# Set success only when the result was actually confirmed by the host.
host_verified = False
outcome = "unverified"

event = record(
    "local-consented-evidence", packet,
    consent=True, sensitivity_reviewed=True, sensitive=False,
    secret=key, site_family="consented-site-family",
    case_key="stable-task-family-trial-001", variant="baseline",
    outcome=outcome, host_result_verified=host_verified,
    duration_ms=(time.perf_counter()-start)*1000,
    # Optional ONLY when an operator actually labels visual necessity:
    # visual_label="visual_needed", visual_label_verified=True,
    # Optional ONLY when actual provider usage was returned:
    # input_tokens=..., output_tokens=...,
    # cached_input_tokens=..., token_provenance="provider_reported",
)
```

Records include only: HMAC pseudonymous site/task keys; categorical role/route/reason/age/size buckets; consented operator label; host-attested outcome; total duration; optional actual provider token counts; and explicit false action-qualification fields. They **do not contain** task strings, control labels, DOM text, candidate IDs, page URLs, screenshots, cookies, prompt text or model outputs. Records are created exclusively as private local files (mode 0600 on POSIX where supported).

**Limitations:** anonymised-looking hashes alone are insufficient privacy protection; HMAC privacy depends on safeguarding the secret. A malicious or inaccurate host can fabricate an outcome, so these are **host-attested, not independently authenticated** records. This code does not independently prove consent or certify whether a webpage is sensitive. Do not publish raw evidence without explicit review.

## 3. Matched task evaluation: paired success, latency and real tokens

Collect records using the **same** site family, case/trial key and HMAC secret for `variant="baseline"` and `variant="optimized"`.

```bash
python tavi_field_data.py local-consented-evidence
```

The report provides matched-case counts, verified outcomes, success rate, Wilson 95% intervals, median/p95 latency, and **paired provider-reported** input/output token deltas only when both variants report usage.

Unverified cases are excluded from success-rate calculations. Duplicate variant records for a single trial **fail closed** rather than silently cherry-picking. This is a data analysis path, not an uncontrolled browser-task runner. To claim real-world performance improvements, collect enough **independently verified, consented real tasks**, balanced across sites/task families, and register task definitions and pass conditions before experiments.

## 4. Train an optional, non-deployed visual-review model

`tavi_escalation_train.py` builds a deterministic L2-logistic advisory classifier from **operator-verified** labels on already unique/exact supported-host controls. Labels must be `visual_needed` or `visual_not_needed`, and must come from actual review, never invented outcomes.

```bash
python tavi_escalation_train.py local-consented-evidence \
  --candidate-output candidate-visual-review.json
```

This is deliberately strict:
- At least **80 distinct labelled task cases across eight site/task families**.
- Grouped holdout by pseudonymous site/task family (minimum two held-out families and 20 examples in each side); no repeated family between train/test.
- Both labels required in train and holdout; conflicting duplicated labels reject the dataset.
- Reports held-out confusion matrix, Brier score, baseline Brier, false-negative rate and sample counts.
- Learns only whether to **suggest additional visual review**. No raw text or screenshots are features.
- Candidate output is exclusive-create, not automatically deployed. `may_click=false`, `may_skip_ocr=false`, `automatic_probability_qualified=false`, and `model_adopted=false` are explicit and enforced.

**No real dataset has been submitted in this implementation**, so no real model has been trained or validated. The unit tests use fabricated synthetic labels solely to test split isolation and training code. Once real data exists, evaluate with site/task-family holdout, calibration, false-negative audit, real action outcome measures and manual review. Any future action model needs its **own** independent safety qualification; the failed target auto-action confidence gate remains closed.

## 5. Reproducible checks and next dependencies

```bash
python -m unittest -q test_provider_usage test_field_data test_escalation_train
python -m unittest -q
```

The existing local Chromium generated-page evaluator remains the only executable browser-click path in the repository. Actual user-site tasks must be run by a separately authorised host with per-action verification and explicit user permission.

Before claiming frontier-level competitiveness, run pre-registered matched evaluations on consented tasks, recording actual full-task wall time, total provider usage, retries, failures, recovery rate and final success on the same hardware/driver/model. A passive observer and a classifier are not a trained general computer-use agent.
