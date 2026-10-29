# Tavi v0.16: review every required capability

This release adds `coverage-review`: an offline packet and answer-validation workflow for the current Codex chat. It keeps the full task context, identifies support for each operation across candidate skills, and binds a provided reply to the exact task/inventory snapshot. File and stdin inputs work without model assets, account access or configuration. It makes no network/model call and writes no task history.

Validation rejects changed snapshots, missing or repeated requirements, and unknown or repeated skill IDs. A valid reply is not proof of semantic correctness, the reviewer's identity, or skill code behavior. Probability stays null; installation and execution remain separate. Missing coverage suggests the existing AwesomeSkill discovery workflow.

In a frozen native-model experiment, hybrid review scored95/96 on both a new authored set and an inspected regression set; every condition's accuracy exceeded90%. The balanced Codex model reviewed77/71cases in25.5/24.6-second batches. These are authored policy observations, not a general success rate or computer-use speedup. One false local coverage prediction bypassed review in each set. The local coverage experiments remain inactive. Sanitized cases and measured results are in benchmarks/coverage-v0.16.

Accepted routing and target weights are unchanged. Pixel confidence remains unqualified for automatic actions. Claude remains offline as requested. See Features-coverage-review.md for commands, examples and limits.
