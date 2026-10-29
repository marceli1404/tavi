# Tavi v0.13 — confirmed95% automatic-button policy

The local user confirmed that the intended comparison is confidence **greater than or equal to95%**. The local configuration now enables that rule for routine buttons within the user request. Portable example configuration leaves automatic actions disabled until its owner opts in.

The rule uses the unrounded target probability:0.95 qualifies, while0.9496 does not, even if the display rounds it to95.0%. The percentage remains a synthetic target-match estimate, not measured action safety, permission or success probability.

## How it works

`propose` and `propose-stream` now attach an auto_click policy result. With automatic actions enabled, a qualifying proposal is marked `automatic_click_candidate`. Below-threshold, ambiguous, missing, negative-context or noninteractive proposals remain withheld or follow the existing review path. An explicit Codex rejection or request for an image cannot be overridden by a high score.

The current computer-use agent can carry out a qualifying routine button action without a separate per-button Codex review call or another user prompt, provided its supported driver verifies the current target and existing authorization. Actions still subject to host confirmation requirements remain subject to those requirements.

The OCR stream itself has no input-action backend and does not click. It remains a local recognition/proposal process. The physical click is performed by the host's supported computer-use driver. Tavi does not install a background clicker, modify built-in Computer Use controls or send OS input through an alternate backend.

## Driver integration

`tavi_actions.AutoClickSession` implements the execution gate for host adapters. Construct it with `enabled=True` only when the owner enabled the policy. Call `perform(proposal, task=..., inspect=..., click=..., verify=...)` using callbacks from the supported host driver.

`inspect` supplies trusted live facts: authorized/routine/visible/enabled/is_button all true; requires_confirmation false; matching task, image hash, candidate ID and label; and verified coordinate mapping. These facts must come from current UI inspection and task context, not from OCR text or the confidence score alone. The image hash must reflect a current driver observation, not simply the old saved file. Original screenshot coordinates must be mapped correctly to the current driver's target space.

Proposals expire after five seconds by default, checked before and after inspection. A driver adapter may set a bounded age limit up to30 seconds; the host must still verify current UI state. Expired or changed proposals require a fresh proposal, which can use the warm OCR session.

Each click attempt consumes its proposal within the action session, even if the click outcome or verification fails. Concurrent duplicate requests are serialized. No failed or uncertain click is retried automatically. Do not resubmit old proposals after restarting a host session; reobserve and propose again. A host callback failure does not establish that an input action failed to happen.

## Configuration

The actual local tavi.config.json is enabled following the user's explicit instruction. The distributed example is:

```json
"auto_click": {
  "enabled": false,
  "threshold_percent": 95,
  "routine_buttons_only": true
}
```

Configuration is read by the CLI at startup; a warm process should be restarted after policy changes. Individual stream requests cannot enable automatic actions or hosted execution. `propose --execute` retains its existing meaning of a headless Codex review; it is not a physical mouse command.

## Verification and limits

All179 tests pass. New tests cover exactly95%, higher scores,94.96% rounded to95, invalid/missing raw scores, disabled policy, target and task bindings, changed image/label/coordinates, expired/future proposals, expiry during inspection, live enabled/button/visibility/authorization requirements, host confirmation, reviewer rejection, concurrent duplicates and uncertain/failed outcomes. Driver execution tests use controlled mock callbacks; no native application button was clicked during development.

Actual local OCR marked the Go fixture as an automatic-click candidate and withheld the known documentation illustration. The source and installed Tavi skill describe the host action flow. Main routing and target-model weights are unchanged. Independent real-screen calibration is still pending; a95% estimate is not a95% validated guarantee. No website deployment or public release update is included in this local change.
