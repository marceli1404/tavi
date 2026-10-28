# Tavi v0.3 — routing controls and model lifecycle

## Additions

- Speed/quality/auto preferences, model exclusions, skill exclusions, and structured explanations.
- Native batch routing with one model/catalog load, per-entry errors, no task execution and overwrite refusal.
- Doctor checks trained-versus-installed skill metadata, required policy skills and weight integrity.
- Versioned CPU refresh: new candidates, logs and evaluations; optional guarded activation with concurrent-config checks; previous models retained.
- Rollback restores only the previous model pointer and preserves other current settings.
- Relative model paths resolve against the configuration file directory, not the current working directory.

## Batch example

Save tasks.json:

```json
[
  {"id":"quick","prompt":"Say hello","preference":"speed"},
  {"id":"layout","prompt":"Fix a mobile responsive layout","preference":"quality","exclude_models":["gpt-6-astra"]},
  {"id":"unclear","prompt":"Do it"}
]
```

Run `python tavi.py batch tasks.json --output results.json`. Each result preserves its ID/index and either a decision or an error. Unsupported fields (including execute) are rejected per entry. A batch can report errors and valid results together; the CLI exits1 if any item is invalid.

## Verified observations

- Initial doctor:147 trained skill names versus148 installed; tavi-decision identified as new, no other drift.
- Live CPU refresh trained a148-label candidate. Tier accuracy96%, skill recall@3 100%, external accuracy98%, selected precision88.2%; no-skill accuracy dropped from16/19 to15/19.
- The first promotion gate omitted the no-skill metric and accepted that candidate. We rolled it back, added selected recall/no-skill regression gates and reran refresh. The next candidate was rejected with no_skill_accuracy recorded as the regression, and v1 remained active. The unsuccessful candidate is retained as evidence, not relabelled as successful.
- Live preference smoke check: quality with gpt-6-astra excluded chose gpt-6.1-sol/high, preserved the balanced learned prediction and exposed the explicit-preference mapping in explanation.
-42 tests pass, including preference/override precedence, excluded models/skills, required-policy conflicts, ambiguous tasks, batch partial failures, UTF-8 metadata drift, stale-config activation refusal, rejected-report refusal, rollback preservation and relative-path resolution.
- Bundle verification runs independent inference plus the complete test suite from fresh extraction. No hosted model tasks, GPU inference, website changes or external skill activation were needed in this feature turn.

Accepted v1 weights remain22e0f8b448bee5e0fbfbfb97f9ece31291d3406e11c025679d09a5ca65206482. Rejected refresh candidates and rollback records are local under models/tavi-refresh-* and output/rollbacks, and are excluded from the portable release.
