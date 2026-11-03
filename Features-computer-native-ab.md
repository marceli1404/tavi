# Tavi + Computer: safe Windows integration and honest matched evaluation

**Scope:** development-only, read-only control suggestion. No production
Computer integration or native action backend is installed by this change.
Computer remains the sole operator of windows, clicks, permissions and result
verification. Tavi is a local assistant to *find* controls.

## Integration boundary

The Windows UI Automation integration already on this development branch
offers two experimental read-only paths:

- \`tavi_windows_uia.py\` and \`tavi_native_stream.py\`: a trusted Computer
  host chooses one previously authorised HWND. The long-lived worker accepts
  only \`observe\` and \`recheck\`, returns **one scoped planner projection**,
  and does not accept target window changes, clicks or screenshots.
  Optional native provider: \`uiautomation==2.0.29\`.
- \`tavi_computer_native.py\` and \`tavi_native_uia.ps1\`: a separate
  Windows PowerShell/UIAutomationClient foreground-window collector with a
  read-only Python adapter. It returns a single control hint, explicit
  window binding, optional screenshot fallback request and a host-only
  read-back verification. Its collection remains local and is not a
  capability/authorization token.

These paths **are prototypes, not equivalent production drivers**. The
host must decide which to use and formally review their trust boundary and
native identity stability. An automated model must never be allowed to
choose arbitrary HWNDs or invoke native click methods through either path.

Recommended host steps per interaction:

1. Computer selects an action and internally binds an authorised window.
2. Computer captures its own fresh observation. When its own protocol
   allows native text querying, it sends a bounded scoped target/role query.
3. Tavi reads Windows UIA names, roles and states, and returns a
   \`planner_only\` non-authoritative exact match or review/fallback status.
4. Computer inspects the observation required by its own instructions,
   checks app/process/window identity, current element geometry and
   authorization. Use a fresh host observation before executing each step.
5. Computer performs its own native action and verifies the resulting UI.
   After a stale, ambiguous, disabled or unsupported control, do not
   bypass the restriction through a cached Tavi hint; use host review or
   screenshot-based observation as permitted.

\`Favorites\` is a requested *target label*, not a guaranteed File Explorer
tab on every Windows build. Run a read-only accessibility inspection on
the actual authorised File Explorer window first.

## Preferred integration path and Windows CI status

**Preferred for Computer:** `tavi_native_stream.py` with
`--window-handle <already-authorized HWND>`. Computer, not Tavi or the
planner, must determine which window is permitted. This is a strict
read-only, single-window process; `observe` returns only matching
accessible controls, and a single-use `observation_id` supports
`recheck`. The host must still independently validate immediately
before any authorised click, and must verify the result afterward.

The separate `tavi_computer_native.py` / `tavi_native_uia.ps1`
foreground collector is an experimental alternative; it must not become
the default Computer integration without a review of its foreground
window scope and native identity/coordinate mapping.

[Windows CI run 41686266689](https://github.com/marceli1404/tavi/actions/runs/41686266689)
passed all protocol checks, including Windows-only dependency import,
read-only native-adapter tests, the synthetic browser tests and the
full offline suite (**451 tests** in that run). However, the generated
Tk foreground-window smoke returned `"status":"not_measured"` with
`"real_windows_uia_exercised":false` on the hosted Windows runner,
because it had no usable interactive UI Automation environment. It
therefore supplies **no genuine Windows click, File Explorer or full-task
latency measurements**.

No connected ChatGPT Computer action API is available in this integration
test environment. The A/B reporters validate host-attested results but
**do not call Computer, launch real application tasks, fabricate usage
records or claim a completed Computer-only vs Computer+Tavi experiment.**
A real test needs an explicitly approved interactive Windows Computer
host, native-window and action access, matching planner settings and
provider-reported usage from each trial.

## Matched whole-task evaluation

Use \`benchmarks/computer_agent_ab.py\` to summarise **host-recorded**
Windows task outcomes. This is a **reporting protocol**, not a runner for
ChatGPT Computer or a claim of completed live experiments.

The host must collect matched pairs of the *same task and environment*:
\`computer\` (standard observation) vs \`computer_tavi\` (scoped native
lookup). Both variants must use the exact same planner and model settings,
prompt/task family, host action executor, permissions, UI state and
success-oracle. Alternate trial order, reset to a known initial state each
time, and preserve **all failures**. Use multiple UI families such as File
Explorer, dialogs, settings and forms. Compare the same *complete task*
start-to-verified-outcome interval, including UI observation, planner turns,
fresh rechecks, actions, retries and verification.

The evaluator accepts JSONL (one numeric record per trial) with these
required fields:

\`\`\`json
{
  "trial_id": "example_computer_A",
  "pair_id": "example_A",
  "mode": "computer",
  "task_family": "file_explorer",
  "task_source": "controlled_fixture",
  "planner_id": "same_model_and_prompt",
  "executor_id": "same_computer_host",
  "environment_id": "same_reset_vm",
  "success": true,
  "outcome_verified": true,
  "duration_ms": 1200,
  "screenshots": 3,
  "native_observations": 1,
  "actions_attempted": 3,
  "unexpected_actions": 0,
  "provider_tokens": {
    "input": 1000,
    "output": 250,
    "source": "provider_reported"
  },
  "provider_cost_usd": null
}
\`\`\`

**Example numbers above are invented schema examples, not benchmark
results.** Add the second record with the *same pair_id*, mode
\`computer_tavi\`, and identical planner/executor/environment/task-family
metadata. Use anonymous IDs only. Do not include screenshots, prompts, URL
strings, private filenames, credentials or UI labels in trial logs. Real
tasks require permission and verified outcomes; the evaluator does not
independently prove the host's claims.

Run the evaluator on completed host records:

\`\`\`bash
python benchmarks/computer_agent_ab.py private_matched_trials.jsonl \
  --output computer_matched_summary.json
\`\`\`

No input file => **no results**. The tool rejects unmatched pairs,
duplicate trials, incompatible planner/executor/environment, unknown
fields, invented estimated token counts and missing outcome checks.
For usage, only identical pairs with **provider-reported** input/output
tokens contribute to token savings. Missing usage is \`null\`, **never
zero**. Cost is reported only when both sides provide host-verified
invoiced prices; no pricing is inferred from a token count. Positive
unexpected actions fail the safety indicator even if tasks succeeded.

Sample tests contain fabricated *controlled-fixture* records solely to
exercise the arithmetic and failure/validation contracts, not for
performance advertising.

## What remains unmeasured

There is **no** authorised Computer host session, private provider-usage
feed, true File Explorer experiment, live Windows screenshots or native
OS interaction available to this code review. The earlier ~26.6× figure
was a local Chromium route comparison—not a Windows Computer benchmark.
The earlier ~85% token result measured compact JSON under offline
tokenizers—not provider billing.

A real end-to-end comparison requires a connected Computer implementation
to supply both executed tasks and trustworthy per-task metering. This
repository code does not modify the ChatGPT Computer runtime or its
instruction requirement to inspect a full observation before acting.

Safety note: Windows UI Automation providers can be incomplete, dynamic,
or transiently unavailable. Handle access and bounds are not permanent
security capabilities. Keep the fallback and independent Computer
authorisation checks even when a Tavi match is unique.
