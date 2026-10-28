---
name: tavi-decision
description: Use the locally trained Tavi model to recommend a Codex model, reasoning level, installed skills, or whether to search for a missing agent skill. Use for Tavi requests and workflow routing decisions.
---

# Tavi decisions

Set the Tavi checkout path below to your own installation before using this skill. Run commands from that checkout. It uses NumPy and saved Tavi weights; Laya is an optional comparison backend, not the default inference engine.

For a task, run `python tavi.py route TASK --plan` from that directory using a structured argument array or properly quoted input. Preserve explicitly requested models with `--model` and skills with `--skill`. For raw offline predictions, `python tavi.py predict TASK` needs no Codex inventory, Laya or network.

Use the result as advice:

- `backend` must be `tavi-neural-cpu` to report an independent Tavi decision.
- `model.selection=learned-tier-policy-map` means the network predicted a workload tier and configured policy mapped it to an available model. It does not establish which commercial model is empirically best.
- Read selected skills' actual instructions before applying them. Required user workflows still apply; Tavi's classifier is not a complete policy engine.
- If Tavi selects tavi-decision itself, do not recursively invoke the router. A completed routing call already satisfies that selection; rerun only when the task or relevant inventory changes.
- Respect `needs_review`, unavailable inventory and explicit choices. Scores come from synthetic-policy training and are not calibrated task-success probabilities.
- A launch plan does not change the model of this conversation. `--execute` starts a separate read-only CLI task; use it only when that execution is within the user's requested scope.

When a capability is missing, `python tavi.py discover QUERY` searches public GitHub repositories. Inspect a specific skill with `python tavi.py review-skill OWNER/REPO PATH/TO/SKILL.md --task TASK`. Review reports pin commits, hash source files, flag patterns, report licence/dependency evidence and detect duplicates. Static checks do not prove safety or compatibility.

`review-skill --stage NEW_DIRECTORY` saves passive source for inspection. It does not install or run that source. Do not stage in an active skill directory. Download recommendations do not grant execution or installation authority.

For reproducible training/evaluation and known limits, read the project's README.md and models/tavi-v1/Model-Card.md when needed. Task recording is off by default; `--record` saves the full prompt locally. `feedback` saves explicit labels/observations for a recorded decision and never silently retrains weights.

`doctor` reports inventory drift and validation readiness. `refresh` defaults to expanding added skill labels while freezing the accepted base, when existing metadata is unchanged; `--strategy full` requests complete retraining. Activation requires `--activate`, unchanged baseline gates and separate new-label acceptance. Skills without labelled validation/acceptance examples cannot be silently promoted. `rollback` restores the previous model pointer and keeps other current settings. The portable default model is selected by models/default-model.json; explicit --model-dir still selects a particular artifact.

If the runtime, configured project path or weights are missing, disclose that Tavi did not run and continue using ordinary judgement. Do not report invented model outputs.
