# Compact exact-control responses

Available in Tavi v0.22. This changes response representation, with no model or action-policy changes.

For batches of targets from one fresh host observation, send `"compact": true`
to `target-controls-stream`. Every request still supplies its snapshot and queries.
The resolver retains no observation between requests. The default response remains
`tavi-control-batch-v1`.

```json
{"id":"step-1","snapshot":{"...":"the complete current host snapshot"},"queries":[{"id":"open","task":"Open results","target":"Go"},{"id":"close","task":"Close preview","target":"Close"}],"compact":true}
```

The response uses `tavi-control-batch-compact-v1`. Common observation fields appear
once in `shared_proposal_fields`. Expand each proposal as:

```python
proposal = {**response["shared_proposal_fields"], **entry}
```

The expanded proposals contain every original field. Query IDs, task hashes,
target/context, status, reason, age and candidate remain per query. The batch also
retains `requires_live_host_check: true`, `authorization_granted: false` and
`executed_actions: false`. A caller must verify the actual current control using
its supported host tools before acting within the user's request. This format
provides no learned probability and does not enable automatic clicks.

## Measurement

`benchmark_control_compact.py` compares the same resolved synthetic batch in both
formats. Full JSON reconstruction and actual CLI parity pass for unique, missing,
ambiguous and unavailable controls. Focused tests additionally cover stale/future
observations, detached results, authority flags, invalid options and recovery.

| Queries | Standard bytes | Compact bytes | Payload reduction |
|---|---:|---:|---:|
| 1 | 988 | 1,024 | -3.6% |
| 10 | 7,152 | 3,516 | 50.8% |
| 100 | 69,295 | 28,939 | 58.2% |

Use standard output for a single query. Compact encoding adds approximately
0.10 ms for 10 queries and 0.89 ms for 100 queries in this run. These figures cover
local response encoding only; CPU training was active. They do not measure
observation acquisition, transport, hosted inference, agent reasoning, clicks or
app response. No full computer-use speedup or model token-count claim follows.

Exact trials and source hashes: `output/control-compact-20261102/report.json`.
