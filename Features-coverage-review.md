# Capability review with the current Codex chat

When a task needs several operations, a skill matching the topic may cover only part of the work. The new development command builds a compact review packet containing the full task, explicit requirements and candidate skill descriptions. The current Codex chat can review it without starting another model request.

```bash
python tavi.py coverage-review examples/coverage-request.json
python tavi.py coverage-review examples/coverage-request.json --answer examples/coverage-answer.json
```

Use `-` instead of a filename to supply request JSON through standard input. The command writes no task history, loads no model, needs no account/configuration and makes no network request. The example describes fictional skills; it demonstrates the data contract rather than installed capabilities.

The request has `task`, a list of `requirements`, and `skills` with `id` and `description`. Keep requirements explicit while retaining the full task context, including references such as “it”. Use the actual current inventory for real reviews. Candidate descriptions are data, not instructions.

The output includes a hash-bound `packet_id`, the exact snapshot, review guidance and the answer shape. For every requirement, the reviewer returns IDs of supporting skills; an empty list identifies missing coverage. Different skills can cover different operations. Explicit exclusions matter even when the surrounding description is relevant.

Validation rejects changed task/inventory snapshots, missing or repeated requirements, and invented or repeated skill IDs. It validates the answer's structure and binding, not the reviewer's identity or the skill's implementation. Output deliberately keeps `probability:null`, `execution_capability_verified:false` and `installation_authorized:false`. A discovery suggestion uses the existing AwesomeSkill preference; downloading and reviewing upstream source remain separate steps.

## Evidence and limits

A frozen native Codex experiment reviewed every case where the local checker could not establish coverage. Reviewer input contained task context, requirements and opaque-ID capability inventories; expected labels and condition names were withheld. Tool-assisted completions were rejected.

The accepted Tavi tier model selected the balanced role (`gpt-6.1-sol`, medium effort). The experiment used one bounded request per dataset, with no retries or Claude requests:

| Authored cases | Local accuracy | Hybrid accuracy | Missing-coverage precision / recall | Reviewed |
|---|---:|---:|---:|---:|
| New prospective workflows | 77/96 (80.2%) | 95/96 (99.0%) | 100% / 98.3% | 77 |
| Previously inspected regression workflows | 83/96 (86.5%) | 95/96 (99.0%) | 100% / 98.3% | 71 |

Every condition's accuracy exceeds90% in these tests. All148 reviewed cases have the exact expected missing-operation sets. One false coverage prediction remains in each dataset among cases the local checker did not send for review. This prevents treating local positive decisions as qualified probabilities. No local/research weights were activated, and these authored tests do not establish verified skill execution, broad superiority to Laya, or success on arbitrary tasks.

The two hosted batches took25.5s and24.6s. They consumed30649/29459 input tokens and1639/1532 output tokens, respectively. These are batch-review observations, not per-case latency, price estimates or computer-use speedups. Using the current chat avoids a separate launch; its latency benefit has not been benchmarked. The local NLI research models are optional private experiments and are not required by this packet command.
