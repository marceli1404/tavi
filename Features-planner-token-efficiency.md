# Tavi planner-token and CPU efficiency

**Implementation:** PR #4 development branch, 3 November 2026. These changes reduce
the amount of *trusted observation data displayed to a language-model planner*
and avoid building an unused lookup index. They are not a new general-purpose
computer-use agent or a relaxation of action permission checks.

## 1. Compact, optional planner wire

Existing `python tavi.py observe-stream` input and its full response stay the
**default**. To opt into the planner projection, add `"wire":"planner"` on each
JSON-lines observation request. All requests still require a new
`tavi-control-snapshot-v1`, fresh timestamps, and 1–16 queries.

Example request fragment:

```json
{"id":"observation-1","snapshot":{"format":"tavi-control-snapshot-v1","snapshot_id":"fresh-host-id","captured_at":"2026-11-03T16:00:00+00:00","source":"supported_browser_dom","viewport":[1024,768],"controls":[{"id":"settings-1","label":"Settings","role":"button","context":"Toolbar","visible":true,"enabled":true,"bounds":[24,32,110,38]}]},"queries":[{"id":"q1","task":"Find the Settings control","target":"Settings","role":"button"}],"wire":"planner"}
```

The `captured_at` timestamp above is illustrative and will be rejected as
stale if reused later. A supported host must capture **live**, and no user
or model may manually replace stale evidence to authorise an action.

`tavi-observe-planner-v1` has:

- `snapshot_sha256`: digest of the complete current host snapshot.
- `columns`: `query_id, route, reason, candidate, visual`.
- `rows`: positional values. Exact candidate arrays contain
  `id, label, role, context, bounds`. Missing, unavailable, ambiguous and
  stale controls contain no candidate. OCR observations retain the
  proposal/image binding and review reasons, and are **review only**.
- Mandatory explicit flags:
  `planner_only=true`,
  `requires_live_host_check=true`,
  `requires_fresh_observation_after_action=true`,
  `authorization_granted=false`,
  `executed_actions=false`,
  `action_sequence_authorized=false`.

The projection is **intentionally lossy**: full evidence remains in the
trusted host for audit and eventual authorisation. A projected candidate
does not prove current availability or user permission. A host MUST use its
own fresh authorised observation and control revalidation immediately
before any action; Tavi does not execute actions. DOM text and OCR labels
are untrusted data, not instructions to the planner.

The default full output remains compatible for older consumers. Invalid
wire modes fail closed. Optional `--metrics` appends verbose numeric
telemetry on every response and should ordinarily be disabled when sending
compact messages to an AI; benchmark separately instead.

## 2. Measured offline tokenizer savings

[GitHub Actions run 41680144415](https://github.com/marceli1404/tavi/actions/runs/41680144415)
and its [raw JSON benchmark artifact](https://github.com/marceli1404/tavi/actions/runs/41680144415/artifacts/13251109136)
contain seven fixed synthetic workloads, ranging from one exact control to
16 controls, four absent targets, ambiguous, disabled and stale controls.

| Tokeniser vocabulary | Full JSON | Planner JSON | Tokens saved |
|---|---:|---:|---:|
| `cl100k_base` | 15,490 | 2,328 | **84.97%** |
| `o200k_base` | 15,801 | 2,330 | **85.25%** |

These are totals of **seven equally weighted synthetic JSON messages**,
not real user activity weights or actual provider billing. The 16-exact
case on `cl100k_base` used 5,009 tokens in the full response versus
672 in the planner response: **86.58% less**. Median local projection plus
JSON encoding was **0.04622 ms** across 60 repetitions for that case on
one GitHub Linux runner. These numbers do **not** include model prompts,
schema overhead, history, any planner reasoning, network transfers, or
actual API usage.

Benchmark locally (optional tokenizer dependency; not required for Tavi):

```sh
python -m pip install -r requirements.txt -r requirements-token-bench.txt
PYTHONPATH=. python benchmarks/observe_planner_tokens_benchmark.py --iterations 60
```

The test reports control route/decision parity and zero action
authorisation for every workload. Actual hosted token accounting is still
available **only** through provider-reported usage via
`tavi_provider_usage.py`; a tokenizer estimate is not a replacement.

## 3. Conditional CPU index optimisation

`tavi_controls.resolve_many` now skips constructing a second
**context-keyed** search index only when none of the requested queries uses
a context filter. The main label/role index, full snapshot schema
validation, duplicate detection, canonical SHA-256 observation binding,
per-query expiry checks, and candidate geometry are unchanged.

- Context-filtered queries still build and use the original context index.
- `ControlIndex(snapshot)` defaults to full indexing for general callers.
- Explicitly requesting a context lookup on an unscoped-only index fails
  closed, rather than returning an incomplete or over-permissive result.
- Each query rechecks the snapshot's age independently. **Do not**
  cache a single clock reading across the entire batch: a batch may cross
  the stale boundary while being processed.

Reproduce controlled index-only performance comparisons without a browser:

```sh
PYTHONPATH=. python benchmarks/context_index_efficiency.py --iterations 35
python -m unittest -q test_context_index_efficiency test_control_index
```

The benchmark compares identical 16-query workloads against host
inventories of 64, 512 and 2,048 synthetic controls. It compares the
original full index against context-index elision using the same pinned
observation time for **measurement only**, and verifies exact proposal
identity and snapshot digest parity. Runtime remains per-query fresh.

## 4. Next efficiency checks

1. Measure planner token counts using **real host-reported API usage**
   during approved full task runs, using one shared planner/executor and
   matched baseline/optimised tasks. Include repeated context, prompts,
   retries and OCR/image inputs in cost.
2. Profile `capture_controls` on real consented or sandbox pages
   with thousands of controls. Reduce browser DOM style/layout reads only
   after confirming that visibility and duplicate checks remain correct.
3. Compare end-to-end user-task success, wall time, false-click rates and
   costs. Never infer action safety from a synthetic confidence score.
4. Keep compact packets **planner-only**. Do not build optimistic cached
   command execution or omit live verification to chase speed gains.

**Limitations:** no user website, native Windows OCR, hosted model,
external action, real API billing or independently verified agent-task
completion was measured for the tokenizer/index-only efficiency benchmarks.
