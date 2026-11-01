# Explicit local target-outcome feedback

Available in Tavi v0.20. Recording remains off by default. These commands do not capture screens, click, call a hosted model, load routing inventory, train weights or qualify automatic actions.

Generate a normal saved proposal with the current helper and save its JSON as UTF-8. It now includes model_evidence with the target-model weights SHA256 and feature schema. Old proposals lacking that uniform fingerprint are rejected rather than assigned a guessed model.

Create an observation naming the exact proposal and proposed candidate. Allowed fields are:

- proposal_id and candidate_id: copied from that proposal.
- target_match: correct, incorrect or unverified.
- action_outcome: success, failure or unverified. Grade a result only when an action on this candidate was actually observed; otherwise use unverified.
- actual_role: button, link, tab, checkbox, switch, radio, menuitem, textbox, combobox, noninteractive or unknown.
- evidence: an operator observation,1–4000characters. This explicitly supplied text is retained locally.

A neutral observation template can be created without inventing a result:

```python
import json
from pathlib import Path
p = json.loads(Path('proposal.json').read_text(encoding='utf-8-sig'))
candidate = p['review_packet']['proposed']
assert candidate, 'Feedback requires a proposed target'
observation = {
    'proposal_id': p['proposal_id'],
    'candidate_id': candidate['id'],
    'target_match': 'unverified',
    'action_outcome': 'unverified',
    'actual_role': 'unknown',
    'evidence': 'Not evaluated yet; no action outcome verified.'
}
Path('observation.json').write_text(json.dumps(observation, indent=2), encoding='utf-8')
```

After checking the actual target/result and editing that observation as appropriate:

```sh
python tavi.py target-feedback proposal.json observation.json
python tavi.py target-feedback-summary data/target-feedback
```

Use --directory on the recording command to select another local store. JSON inputs are limited to2MB; summaries accept at most10000files/32MB. A new UUID file is appended for each explicit observation. Existing files are not overwritten. No raw task, target label, nearby OCR text or screenshot pixels are automatically copied into feedback; their bindings are hashed. Operator evidence can itself contain whatever text the operator explicitly supplies.

## Interpreting a summary

Records are grouped by target-model hash and feature schema. Target-match assessments and action outcomes have separate denominators. Unknown outcomes remain visible. Conflicting known assessments of the same observation are marked conflicted and excluded from that rate rather than resolved silently. Repeated identical observations count once; copied identical event files are separately reported. Coordinates and raw scores are numerically canonicalized, so equivalent JSON number encodings do not inflate counts.

A distinct observation is a model/image/task/target/candidate/geometry/raw-score binding. Different candidates or scores can share one image-task binding; neither count establishes independent trials. Summaries expose unique image hashes and image-task bindings alongside observation counts. Raw score bins use unrounded values, including a separate0.95–1.0bin; bins do not grant action permission.

These are self-selected operator assessments, not authenticated host facts, calibrated success probabilities, representative field samples or full-screen recognition coverage. No-candidate proposals cannot receive candidate feedback. automatic_probability_qualified and qualification_changed remain false. A100% recorded rate is not a100% guarantee. Writing feedback never changes model files or the existing failed-field-qualification guard.

## Validation

Public-package tests cover explicit binding rejection, model/schema separation, raw score boundaries, unknown/action separation, duplicate/conflict handling, minimal retained data, offline CLI operation, existing action safeguards and a real synthetic-proposal integration. A saved synthetic fixture smoke check writes two contradictory operator assessments and confirms one conflicted observation, an unknown match rate and no known action outcome. It is software evidence, not newly collected field data.
