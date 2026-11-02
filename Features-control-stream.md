# Persistent exact-control resolver (v0.21)

`python tavi.py target-controls-stream` keeps the local resolver process open for JSON-lines requests. It emits a ready record, then one response per request, and exits on EOF. This avoids repeated Python/CLI startup. It does not capture a screen, acquire DOM/accessibility data, call a model, use the network, authorize or perform input actions.

Each request supplies its entire current `tavi-control-snapshot-v1` observation and queries, using the same schema as `target-controls-batch`:

```json
{"id":"step-1","snapshot":{"format":"tavi-control-snapshot-v1","snapshot_id":"host-frame-1","captured_at":"2026-11-01T20:00:00+00:00","source":"supported_browser_dom","viewport":[800,600],"controls":[{"id":"go","label":"Go","role":"button","visible":true,"enabled":true,"bounds":[10,10,80,30]}]},"queries":[{"task":"Open the result","target":"Go"}]}
```

The timestamp above is illustrative and will be stale: the supported host must supply its actual observation time. The server retains no snapshot between requests. Resubmitting an observation does not refresh it: the unchanged resolver checks original capture time for every query, with five-second freshness and future-clock rejection. No offline option is accepted. A supplied source marker does not authenticate capture. The host must still check current control identity, state, geometry, task authorization and required confirmations, perform any action through its supported input API and verify the result.

Results retain `probability:null`, `requires_live_host_check:true`, `authorization_granted:false` and `executed_actions:false`. Stream metadata adds request ID and `observation_reused:false`, meaning no server observation cache was used. It does not certify a new capture or create an action receipt. Missing snapshots cannot reuse a previous request. This does not qualify the pixel model for automatic clicks.

Only `id`, `snapshot`, `queries` fields are accepted; ID is optional, nonempty and at most80characters. Duplicate JSON fields are rejected, including nested objects. Each line is bounded to2MB UTF-8; an oversized line emits an error and terminates without interpreting its remainder. Other request errors emit an error record and allow the next request. Existing bounds of10000controls/1000queries and exact-label/role/context matching remain. No config or model inventory is needed. Close stdin at session end.

## Verification and measured limits

Five targeted tests cover direct batch-result parity, null probability/no authority, stale/future/ambiguous/disabled controls, required observations, changed labels, rejected offline fields, malformed JSON, duplicate fields, size bounds and recovery. The development suite passes394tests. Public package checks are recorded in the release notes. Missing-config CLI succeeds in the benchmark.

12 alternating paired synthetic requests measured one-shot CLI median158.881ms versus warm stream0.248ms; startup142.354ms separately. Unique/missing/ambiguous control outcomes match exactly except naturally elapsed age. The one-shot includes startup/file reads; stream requests include pipe serialization and parsing. Both receive supplied synthetic observations. This is not an independent UI or whole-agent speed test and excludes observation acquisition, live verification, agent reasoning, clicks, app response and hosted image inference. Raw source-hash-bound evidence: `output/control-stream-speed-20261101/report.json`. No production website speed claim is changed. Available in v0.21.
