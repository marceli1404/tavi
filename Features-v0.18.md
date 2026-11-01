# Tavi v0.18: repeated control lookup with clear quality advice

Tavi can now validate and index one supplied control observation for several exact lookups. Context-quality reporting also advises agent review when the recorded context checks do not exceed 90%, even if a raw model score is high. Accepted model weights, selected routes and action-qualification gates are unchanged.

## One observation, several targets

```sh
python tavi.py target-controls-batch snapshot.json queries.json --offline
```

`queries.json` contains 1-1,000 requests such as:

```json
[
  {"id":"install","task":"Locate Install","target":"Install","role":"button"},
  {"id":"source","task":"Locate GitHub","target":"GitHub","role":"link"}
]
```

Use the [control snapshot schema](Features-control-grounding.md) for `snapshot.json`. Both files are bounded to 2 MB. IDs are optional but must be unique when present; unknown action flags fail. Offline results are replay only. For a genuinely current observation, omit `--offline`; every result still requires a live host check before an action. A new or changed UI observation requires a new index.

The library equivalent is `ControlIndex(snapshot).resolve(task,target,role=...,context=...)`, or `resolve_many(snapshot,queries)`. The copied observation is isolated from later input/result mutation. Every query rechecks capture age; indexing never refreshes the capture time. Exact roles, normalized names, optional exact context, visibility, enablement, geometry, ambiguity and future-time checks remain. No fuzzy selection is introduced. The single-target command retains its scan path.

A batch contains independent lookups, not authorization for a series of clicks. Proposals retain `probability:null`, `requires_live_host_check:true`, `authorization_granted:false` and `executed_actions:false`. The supported driver must check the current intended control before each action and verify its result. Tavi adds no capture or input backend.

## Measured preparation

The offline benchmark uses supplied synthetic inventories, 12 queries and 10 alternating-order rounds, with a frozen logical clock:

| Controls in observation | Previous repeated lookups | Indexed batch including setup | Ratio |
|---|---:|---:|---:|
|10|0.518 ms|0.115 ms|4.51×|
|1,000|42.191 ms|5.071 ms|8.32×|

These are in-memory preparation timings. Capture, file parsing, process startup, agent reasoning, physical input and UI response are excluded. A prepared query's 0.005 ms median at 1,000 controls excludes the 4.704 ms index setup, which is included in the batch column. This is not an 8× whole-agent or whole-computer-use result. Small one-shot timing differences are not claimed as improvements.

200 seeded differential cases match the previous resolver exactly. They vary Unicode/context, roles, duplicated labels, states, viewport geometry, timestamps and replay mode. The source and clean package test suites cover expiry inside a batch, future times, mutation isolation, malformed nonmatching controls, bounded queries and rejected action flags.

Raw measured results, protocol, parity cases and original benchmark source are under `benchmarks/control-index-v0.18`. Reproduce a fresh offline run with:

```sh
python benchmarks/control_index.py output/control-index-replay
```

The command preserves an existing run instead of overwriting it. Timings vary by machine and workload; it performs no browser or input actions.

## Context-quality advice

Each probability report now includes recorded tier/external context accuracy, case count and whether it is strictly above 90%. Missing or zero-case evidence remains unknown; aggregate evidence is not substituted for a missing context. An agent-review reason is added for either head's shortfall or unknown evidence. Exactly 90% does not pass a strict above 90% requirement.

This is authored-policy validation, not measured task-success probability or field action qualification. `affects_routing:false` remains explicit: learned distributions and chosen routes do not change, and this advice is not a request for additional user approval.

## Visual role ambiguity

A controlled native BUTTON and native A/link pair rendered to exactly identical 1280×720 pixels and identical current OCR/image features. The visual target model scored both 0.9999966 despite their different roles. Source fixtures, observed DOM facts and the hash-bound result are under `benchmarks/control-identity-v0.18`; screenshots remain excluded from the package. This controlled pair does not estimate natural-field prevalence or action success.

The 95% pixel policy remains configurable, but the current target model is still unqualified for probability-based automatic actions. Exact host facts carry no invented learned percentage. No rejected research models, private captures, local configuration or project ledger are distributed. Claude support remains available; no live Claude sign-in was used for this release.

## Release checks

246 public source tests pass. The package uses an explicit file allowlist and per-file SHA256 manifest. Accepted router and target weights are unchanged.
