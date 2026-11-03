# Computer-use efficiency track — control matrix and warm routing

Tavi v0.24 is a **CPU decision/routing model and proposal helper**, not a
standalone graphical computer-use agent. It does not capture or operate a
computer. This track optimizes the information supplied to a *supported host
agent*, while preserving that agent's authorization and live verification.

## 1. New opt-in matrix transport

`python tavi.py target-controls-stream` already avoids process startup for
each request and resolves exact host-provided controls before trying OCR or
hosted vision. The caller can now choose a **lossless columnar** response:

```json
{
  "id": "frame-17",
  "compact": "matrix",
  "snapshot": {
    "format": "tavi-control-snapshot-v1",
    "snapshot_id": "host-frame-17",
    "captured_at": "2026-11-03T10:00:00+00:00",
    "source": "supported_browser_dom",
    "viewport": [1280, 720],
    "controls": [{
      "id": "submit-1", "label": "Submit", "role": "button",
      "context": "Form", "visible": true, "enabled": true,
      "bounds": [600, 600, 100, 40]
    }]
  },
  "queries": [
    {"id": "submit", "task": "Submit the form", "target": "Submit", "context": "Form"},
    {"id": "cancel", "task": "Review cancel button", "target": "Cancel", "context": "Form"}
  ]
}
```

The timestamp above is illustrative, not a usable current observation. The
host must supply a freshly captured observation in **every** request. Omitted
`compact` still returns the original batch; `true` still returns the existing
compact batch. `"matrix"` is the new opt-in mode.

Output is `tavi-control-matrix-v1`. It contains the original batch's snapshot
hash and authority flags, a `shared_proposal_fields` object, ordered
`columns`, and `rows` containing values in precisely that order.
`query_id` is the only optional column, represented by null when absent.
Use `expand_matrix(output)` from `tavi_control_matrix.py` to reconstruct the
exact original `tavi-control-batch-v1` response. Row order and query/task
identities are preserved, as are candidate coordinates, all review reasons,
all hashes, and explicit lack of learned probability and action authority.

**Safety:** Matrix output cannot click, authorize an action, infer success,
reuse a stale screenshot or skip the host's current-control recheck. The
existing five-second freshness gate still applies. Permission, task context,
control identity and execution results must be checked by the trusted host.
Matrix mode doesn't change model weights or button-confidence qualification.

## 2. Measuring what changed

```sh
python -m unittest -q test_control_matrix
python benchmarks/control_matrix_benchmark.py
python -m unittest -q
```

The benchmark compares JSON UTF-8 bytes and local representation-conversion
latency on 64 deterministic synthetic queries. These are *not* measured
commercial-model tokens or whole-agent timings. Compare `full`,
`compact`, and `matrix` against the same batch. Record the raw results from
your actual host session before claiming a speedup.

### First GitHub Actions result (3 November 2026)

The Linux/Python 3.12 workflow at
https://github.com/marceli1404/tavi/actions/runs/41616125275 passed all
22 focused tests. Its 64-query synthetic JSON measurements were:

| Format | UTF-8 bytes |
| --- | ---: |
| Full v1 | 48,436 |
| Existing compact v1 | 24,279 |
| New matrix v1 | 18,294 |

Matrix output was **62.23% smaller than full** and **24.65% smaller than
existing compact**. Local conversion medians were 0.62917 ms for compact
and 0.67294 ms for matrix on that CI runner. Thus matrix conversion itself
was slightly slower, not faster. Real LLM token counts and end-to-end
computer-use latency are still unmeasured; JSON bytes are only a proxy.


### Warm offline inference and brief decisions (3 November 2026)

Use `python tavi.py predict-stream` to keep the checksummed CPU model and
feature vectorizers loaded between independent requests. The JSON-line stream
has strict request sizing and duplicate-field rejection and exposes no
network, hosted model, UI input, or permission backend:

```json
{"id":"step-1","prompt":"Inspect the navigation settings","detail":"brief"}
```

The default `detail="full"` has the same prediction fields and default top
eight skills as one-shot `predict`. `detail="brief"` defaults to three
skills and **intentionally omits** verbose calibration diagnostics. It
retains all tier scores, the ranking scores and thresholds, the vocabulary
coverage and every `review_reasons` item, together with calibration status
and an explicit false real-world-success-probability claim. Use full detail
when inspecting the exact calibration evidence.

A GitHub Actions Linux/Python 3.12 run at
https://github.com/marceli1404/tavi/actions/runs/41618164875 passed
**70 focused tests** (22 control and 48 model/compatibility), built a portable
hash-checked archive with 268 source/model files, and measured 12 paired
synthetic/offline prompts:

| Measurement | Result |
| --- | ---: |
| One-shot CLI median, including Python and model load | 148.606 ms |
| Warm request median, after startup | 1.142 ms |
| Local median latency ratio | 130.12× |
| Warm process startup, separate | 146.119 ms |
| Full response JSON bytes across 12 prompts | 36,559 |
| Brief response JSON bytes across 12 prompts | 11,982 |
| Brief transport-byte reduction | 67.23% |

These are **local process/transport figures**, not achieved speed on a
desktop task or commercial model token counts. A single CI runner and
sequential synthetic requests cannot establish a universal speedup; startup
amortizes only after multiple requests. The standalone local model weights
were not changed and no computer-control permission gate was lowered.
The accepted model's prior real-screen failure remains relevant.

To repeat the comparison:
```sh
python -m unittest -q test_predict_stream test_model_warm_adapters test_probability_quantization
python benchmarks/warm_prediction_benchmark.py
python bundle_tavi.py
```

## 3. What would make Tavi competitive

The primary optimization target is **verified completed work per token,
second and pound**, not raw classifier accuracy. Build a paired evaluation
from independently labelled, permissioned desktop/browser traces:

1. Establish a baseline with the same tasks, host, model, hardware and
   authorization policy. Record completed-task accuracy, end-to-end elapsed
   time, input/output/cache tokens, screenshot bytes, model calls, UI steps,
   retries, and human corrections.
2. Run deterministic host-control matching first, then local OCR, then
   hosted vision when needed. Keep task and current UI bindings, and verify
   changes after acting. Avoid repeated screenshots or reflection calls only
   when the current host state proves that doing so is safe.
3. Train separate policies on **training-only** labelled traces: escalation
   choice (exact host control vs local OCR vs visual review), workflow
   difficulty/routing, and ambiguity abstention. Split by website,
   application and task family to prevent near-duplicate leakage.
4. Collect real positive and *hard negative* targets, including visually
   similar but disabled/hidden controls. Calibrate confidence on independent
   data. Do not enable model-based auto-clicking until untouched field
   validation passes. Synthetic confidence is not sufficient.
5. Benchmark against full/compact/matrix and leading agent stacks on
   identical tasks. Report accuracy versus token and latency curves, not
   cherry-picked cases. Include failure, security/permission and recovery
   rates, with paired uncertainty intervals.
6. Ship a versioned candidate only if completed-task success is non-inferior,
   authority checks remain unchanged, and measured cost/latency improve.
   Keep rollback and the old format as defaults until consumers are ready.

Recommended external benchmarks to adapt (check each licence): OSWorld
and OSWorld-Human for desktop efficiency, OSWorld 2.0 for long-horizon tasks,
and Online-Mind2Web for live web workflows. Their published scores should
**not** be compared directly to Tavi's local proposal speed or synthetic
training accuracy.

## 4. Evidence limits

Tavi's v0.14 field audit rejected the existing 95% automatic-button
qualification: there were 16 unique high-confidence mistakes on checked
real-screen candidates. That block remains in force. The current warm
control stream already offers sub-millisecond local resolution in Tavi's
prior synthetic measurement, but full hosted reasoning and UI latency
remain unmeasured. Matrix mode is a transport optimization, not new model
training or verified agent-level performance.

A training run needs independently labelled computer-use trajectories.
Do not train on benchmark test examples, infer labels from model-generated
answers alone, or publish speculative superiority over GPT/Claude/UI-TARS.
