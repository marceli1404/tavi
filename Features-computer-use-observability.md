# Tavi computer-use observability and real-browser fixture evaluation

**Status:** Implemented on the development branch for PR #4 on 3 November 2026. These are engineering instruments, **not** a new autonomous computer-use model.

## 1. What changed

- `tavi_metrics.py` adds opt-in numeric-only recording of bounded stage timings, p50/p95/max wall time, route counts, screenshot/OCR counts, response UTF-8 bytes, and **only host-reported** input/output/cached-token usage.
- `tavi_observe.dispatch(..., metrics=metrics)` instruments exact DOM resolution and visual-fallback processing without collecting UI strings or pixels.
- `tavi_browser_snapshot.capture_controls(page, metrics=metrics)` measures read-only browser DOM observation, including browser evaluation and validation.
- `python tavi.py observe-stream --metrics` enables a session summary on successful responses. Default `observe-stream` remains unchanged and has no telemetry attachment.
- `tavi_browser_eval.py` runs a browser created by the evaluator, on **embedded local HTML only**. It executes one fixture-only verified click plus four deliberately blocked scenarios per repetition.
- `test_metrics.py` and `test_browser_eval.py` cover limits, source/privacy checks, unmeasured token handling and authorization boundaries. GitHub Actions also installs real Chromium for a separate generated-page evaluation.

## 2. Run the observer and measure cost

Start a warm observation stream with **explicit opt-in**:

```bash
python tavi.py observe-stream --metrics
```

Each incoming JSON line still needs a *fresh host-generated* `tavi-control-snapshot-v1` and one to sixteen queries. Results now include `telemetry` with numeric counters and stage p50/p95. The telemetry contains no URLs, control labels, tasks, prompts, screenshot contents or screenshots. It is in memory until the process exits. It is **not** a complete task recorder.

Programmatically, a host that already has a Playwright page can instrument the same steps:

```python
from tavi_browser_snapshot import capture_controls
from tavi_metrics import UsageMetrics
from tavi_observe import dispatch

metrics = UsageMetrics()
snapshot = capture_controls(page, metrics=metrics)
packet = dispatch(snapshot, [
    {"task": "Inspect Settings", "target": "Settings", "role": "button"}
], metrics=metrics)
metrics.observe(packet)
summary = metrics.summary()
```

When an approved external LLM call returns **actual usage metadata**, the host may add it:

```python
metrics.provider_usage(input_tokens=1200, output_tokens=130,
                       cached_input_tokens=100, elapsed_ms=455.0)
```

The numbers above are merely an **example of calling the API**. Tavi does not fetch billing data or infer hosted tokens. With no usage metadata, `provider_tokens.status` is `unavailable` and token totals are **null**, not zero; a mixture of known and unknown calls is `partial`. Never assert actual token savings from JSON byte savings alone.

The timing sample history is bounded (default latest 512 observations per stage); `count` reports lifetime observations for a live metrics instance. Percentile is nearest-rank within the retained sample window. There is no persistence, uploader or remote telemetry.

## 3. Run an actual, controlled browser fixture

```bash
python -m pip install -r requirements-browser-eval.txt
python -m playwright install chromium
python tavi_browser_eval.py --repeats 3
```

Optional `--output report.json` writes a **new** JSON numeric report using exclusive creation and never overwrites an existing file. The evaluation creates its own isolated Chromium page and uses `page.set_content` with embedded HTML only; attempted remote requests are aborted. It cannot accept a user URL, a browser-session path or an arbitrary website.

Each repetition checks:

1. A unique, visible, enabled **Go** control: Tavi proposes an identity, the test driver captures a *second fresh DOM observation*, verifies candidate ID/role/label/bounds and a unique live Playwright locator, clicks, and verifies the UI changed to the expected result.
2. Disabled control: no click.
3. Ambiguous duplicate controls: no click.
4. Missing semantic control: no click; Tavi requests visual evidence.
5. Control changed between observation and action: fresh recheck blocks the click.

The click is **inside this fixed local test fixture only**. Production Tavi still has **no arbitrary-site click backend**, and the synthetic OCR confidence model still has failed real-screen action qualification. Rechecking before any action, respecting host permissions, and verifying the result are mandatory. Never queue or replay a list of earlier proposals as actions.

GitHub Actions runs both the offline regression suite and a separate real-headless-Chromium fixture job. This covers the browser control observer and the fixture's action/verification path. It does **not** test a model planning real tasks, native Windows OCR, OSWorld, BrowserGym/WebArena, credentials, websites or end-to-end hosted model tokens.

## 4. Next implementation priorities

1. **Permissioned real-world evaluation data:** opt-in capture of task/outcome labels and redacted control metadata in local storage, with default deny for passwords, payment pages and other sensitive data. Split held-out tasks by site/task family and enforce a no-leakage policy. Do not silently collect private user traces.
2. **Real host integration:** connect the DOM-first observation and fresh re-verification contract to the user's *already authorized* browser driver. Keep any mutations behind explicit host permissions, review and result verification. Test navigation, redirects, popups, animation, cross-origin frames, accessible-name quirks and stale/changed geometry.
3. **End-to-end matched benchmark:** record completed-task success, failures, p50/p95 wall time, hosted prompt/completion tokens (only reported), calls, retries, visual fallback share and cost. Compare stable baseline and optimised variants on the same tasks, environment and provider. Use per-task logs with explicit consent and suitable redaction.
4. **Training only after independent labels exist:** generate labelled positive/negative escalation examples, train/evaluate a new offline policy on held-out task families, and calibrate against real-screen outcomes. Keep the current failed auto-action qualification gate closed until a separate safety review passes.
5. **Protocol deltas after correctness:** evaluate revision-tagged, hash-bound DOM observation deltas for non-actionable display only; never treat cached or reconstructed snapshots as current permission to act.

**Do not relax action confirmation thresholds for speed.** Skipping checks based on a synthetic confidence score would make Tavi faster on paper but less reliable and less safe. Avoid asynchronous post-action verification where a failed action could already have caused harm.
