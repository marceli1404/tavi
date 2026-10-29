# Tavi v0.15 â€” provider handoffs and exact control facts

This release adds Claude Code routing plans and an exact-control resolver.
Accepted v4 routing and target-v1 weights remain unchanged. Current pixel
scores remain unqualified for probability-based automatic clicks.

## Claude Code

Use `--provider claude` on `route`, `inventory` or `batch`. Fast, balanced and
deep map to the official haiku, sonnet and opus aliases, separately from Codex
configuration. These mappings are policy, not measured model rankings or proof
of account access.

`provider-status claude --auth` reports CLI version and redacted sign-in status.
Install and sign in separately. CLI 2.1.312 version/help and actual argument
parsing were checked; minimum supported version is 2.1.259. No authenticated
Claude request was performed: the owner chose to keep Claude offline.

`route TASK --provider claude --plan --workspace DIR` prepares a print planning
session with read/search tools, MCP disallowed and permission prompts disabled.
This limits CLI tools; it is not an operating-system sandbox. Add `--execute`
to launch an authorized hosted task using your own account and allowance.

For a full coding handoff, add `--interactive`. Execution requires a real
terminal and uses Claude's native default permissions and approval flow.
No bypass flag, shell interpolation or desktop-provider switching is added.
Review-needed routes withhold their launch plan. JSON output uses UTF-8 even on legacy Windows pipes, preserving non-ASCII skill descriptions.

## Supported-host control facts

`target-controls controls.json --task TASK --target LABEL` resolves an exact
role and label from a supported host's current DOM/accessibility inventory.
It checks unique identity, visible/enabled states, viewport bounds, optional
exact group context and five-second freshness. Ambiguous, unavailable and stale
matches require review. `--offline` permits nonactionable replay only.

The proposal has `probability:null`: direct host facts are not a learned95%
score or permission to click. The host rechecks the live identity, existing
authorization and required confirmations, acts through its supported driver
and verifies the outcome. Tavi adds no capture or input backend.

Thirteen resolver tests and three actual Tavi website controls were checked.
All three host-performed clicks produced the expected pressed state. A saved
one-page microbenchmark over three repeated labels measured0.252ms resolution
versus163.625ms warm OCR preparation. Acquisition, CLI/host round trips, agent
reasoning, input and app response are excluded; this is not full computer-use
speed or field ML accuracy. See Features-control-grounding.md for the schema.

## Validation and limits

Stable source tests cover provider isolation, literal arguments, redacted auth,
normal interactive permissions, absent CLIs, review withholding, control
freshness/ambiguity and existing routing/action gates. The benchmark CLI order
bug is fixed; tool-assisted coding completions are rejected. The restricted
judge supports standard chr/ord/divmod and copy in upstream tests. Rejudging34
saved historical answers preserves every original pass/fail verdict.

Experimental semantic encoders and newly trained candidates remain local and
inactive. They are not bundled here and do not establish greater than90%
accuracy across all evaluations, universal speed or superiority over Laya.
