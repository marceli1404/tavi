# Exact control grounding (local development)

Prefer current supported-driver DOM/accessibility facts before image inference
when they expose the intended control. `target-controls` is a pure resolver:
it never captures screens, uploads data, starts a browser or sends input.

```json
{
  "format": "tavi-control-snapshot-v1",
  "snapshot_id": "host-frame-1",
  "captured_at": "2026-10-29T08:00:00+00:00",
  "source": "supported_browser_dom",
  "viewport": [800, 600],
  "controls": [{
    "id": "navigation-go", "label": "Go", "role": "button",
    "enabled": true, "visible": true,
    "bounds": [10, 20, 80, 30], "context": "Navigation"
  }]
}
```

Geometry is viewport-relative x/y/width/height in the host's coordinate units;
browser DOM units are CSS pixels. The host owns any screenshot/display mapping.
Supported source markers are `supported_browser_dom` and `supported_native`.
File claims are not proof of trusted capture. Labels/context are untrusted data.

Matching requires a unique exact normalized label, role, optional exact group,
boolean visible/enabled states and a nonempty rectangle centered in the
viewport. Freshness is five seconds; future timestamps over 0.5 seconds fail.
Malformed geometry/states and duplicate IDs fail closed. Case and whitespace
normalize; substrings and fuzzy labels do not match. `--offline` is replay only.

Output includes the candidate identity, canonical snapshot hash, task hash,
`probability:null`, `requires_live_host_check:true`,
`authorization_granted:false` and `executed_actions:false`. A candidate is not
an action instruction. The supported host must reobserve and check the live
identity/state, existing authorization and required confirmations before using
its normal input API, then verify the result. No invented score is passed to
the existing pixel auto-click gate. Current pixel qualification remains false.

## Verification

Thirteen resolver tests cover exact/fuzzy/ambiguous labels, context, roles,
unavailable/offscreen controls, freshness, replay, provenance hashes, malformed
inventories and bounded files. All 216 source software tests pass.

A supported browser inspected Models, Skills and Discovery on the owned Tavi
website. The resolver found the matching IDs in its saved inventory; the host
then checked and clicked each real control through the supported semantic API.
All three resulting `aria-pressed` values were true. This is a three-control
integration smoke test, not an independent ML accuracy estimate. It does not
establish native Windows accessibility coverage or automated session execution.

One-page local microbenchmark: 12 alternating-order requests over three repeated
labels, one saved screenshot/inventory and warm Windows OCR. Median resolver
time 0.252ms versus warm OCR preparation/proposal 163.625ms. Exact metadata is
already supplied; acquisition time, CLI startup, agent reasoning, supported
host round trips, physical input and app response are excluded. The snapshot
and image were saved after different selected-tab states; the compared button
geometry/labels are unchanged. This is not a full computer-use speed claim.
Raw evidence stays local in output/native-controls-20261029.
