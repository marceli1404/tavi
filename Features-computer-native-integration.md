# Tavi + Computer: native Windows accessibility helper (experimental)

**Status:** The read-only prototype is implemented in draft PR #4. It has not
been installed into ChatGPT Computer. A host controlling an authorised
Windows desktop must explicitly connect and test it.

## Trust boundaries

Computer owns user intent, window permissions, the full observation,
whether to act, the actual click and post-action verification. Tavi
is a low-overhead, *non-authoritative* accessibility lookup layer.

The native UIA adapter reads only a host-provided HWND (window handle),
and scans a bounded number of descendants for exact requested labels
and control roles. It does not search the desktop, read edit-field
values, invoke controls, click, type, focus, or take screenshots.
It retains all matching duplicates to flag ambiguous controls.
Unsupported, truncated or unavailable UIA trees fail closed.

The planner receives only scoped matching controls and explicit safety
flags, never the entire accessibility tree. A fresh host recheck matches
window geometry plus control identity, role, label, context and bounds.
A successful recheck **does not authorise a click**: Computer must do
its own final live verification, permission check and execution.
Window-relative UIA coordinates are not guaranteed to equal Computer's
native click coordinates (multi-monitor and DPI differences matter).

## Installation and requests

On Windows with Python 3.12+, the optional original UI Automation
Python package is pinned in requirements-native-windows.txt. Install:

    py -m pip install -r requirements-native-windows.txt

From an explicitly authorised Windows host, with a real approved HWND:

    py -m tavi_native_stream --window-handle 123456

The worker accepts JSON-lines and remains loaded for subsequent
observations. Example observation request:

    {"id":"step-1","op":"observe","queries":[{"id":"q1","task":"Locate the selected tab","target":"Favorites","role":"tab"}]}

The response has status "observed", a short-lived observation_id
and a planner-only result. To ask the host-side helper to refresh and
compare that exact observation, send:

    {"id":"step-2","op":"recheck","observation_id":"<exact id returned by observe>"}

Each observation ID is single-use for recheck and expires after five
seconds. At most 64 are retained. Recheck responses report matched
true/false, but always set authorization_granted and executed_actions
to false. A missing label asks Computer to use its ordinary screenshot
route; disabled, duplicate and stale observations do not become clicks.

**File Explorer note:** On different Windows versions/locales, Favorites
may be a tree item, list group or other role rather than an actual tab.
The agent must use the role exposed by the current application.

## Tests and honest limitations

The fake-provider tests run cross-platform and verify exact lookup,
no unrelated control names leaked, changed/moved/disabled/duplicate
controls fail closed, window-handle scope, stale rechecks, one-use tokens,
and that no click, Invoke or focus method is ever called.

A separate Windows GitHub Actions job imports real uiautomation and
runs these contract tests; it does not exercise the user's File Explorer,
desktop, ChatGPT Computer runtime or real end-to-end actions. A live
Windows interactive pilot must be supervised and host authorised.

The optional tavi_native_ab_report.py requires a genuine, consented,
numeric-only paired dataset from a real Computer host. Each task requires
two variants: computer_only and computer_tavi, with the same pseudonymous
task ID, model, executor and test environment. Each record provides
verified success, full elapsed task duration, screenshot count when
available, provider-reported input/output tokens when available and
permission-incident counts.

Do not record task prompts, raw accessibility text, filenames, window
titles, account details, screenshots or model responses. Unavailable
token counts must be null and are not counted as zero. The analyser
includes failed tasks and reports denominators for paired token and
screenshot measurements. No real Computer A/B dataset has yet been
collected, so there are **no verified live task-speed or billed-token
savings** from this integration.

After collecting explicit user-consented pairs in a host-run numeric
JSON array:

    py tavi_native_ab_report.py --input consented-paired-metrics.json --output results-new.json

The report destination must be new; it will never overwrite an
existing report. Use independent task-success checks, counterbalanced
ordering and consistent starting state for a fair comparison.

## Files

- tavi_windows_uia.py — scoped native UIA observation and read-only
  fresh matching, with injected provider option for tests.
- tavi_native_stream.py — persistent single-authorised-HWND JSON-lines
  observation/recheck worker.
- tavi_native_ab_report.py — strict paired numeric evidence validator
  and summariser.
- test_native_windows_uia.py and test_native_ab_report.py — unit
  tests for safety, redaction, pairing and missing-data handling.
- requirements-native-windows.txt — optional pinned UIA dependency.

These changes do not add a production clicking backend, bypass user
consent, disable Computer's full-observation policy or claim Computer
itself has been integrated.
