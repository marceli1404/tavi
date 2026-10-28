# Tavi v3 workload-tier adapter

A residual TF-IDF softmax classifier adds workload-tier corrections to the accepted v2 network. Original weights,148 skill outputs and external-search head are frozen.1053 training/205 validation tier rows combine original labels and newly authored synthetic descriptions. No public coding benchmark prompt or label is fitted. Epoch50 and correction gate0.65 are selected using validation while preserving original-validation accuracy. The feature vocabulary is fit only on training rows.

The adapter retains the base decision when its correction is uncertain. For explicit Python function specifications, a new review prediction cannot withdraw an already confident base recommendation. This is visible migration policy, not a learned claim that every function specification is safe or easy. Existing routing confidence/coverage thresholds are unchanged.

Development checks were used across five retained candidate attempts and are not blind independent evidence. Original50 policy accuracy stays96%; development40 rises75→95%; historical32 probability-check tier accuracy56.25→78.125%. The final post-freeze32-case authored audit rises68.75→93.75%. These are same-author synthetic policy labels, not observed best-model labels.

Eight public coding audit tasks excluded from training still have only4/8 covered routes in both models. Broad coding coverage remains limited. Six completions on two separately fixed public coding tasks all passed; selected routes pass2/2 in both versions, so this does not establish a new task-success advantage. Public historical tasks may be in foundation-model training.

The old calibration is invalid for changed metadata. Fresh32-fit/40-check calibration was rejected because its external-search NLL worsened. Predictions are explicitly uncalibrated; the old v2 calibrated copy remains available. Do not present these scores as real task-success probabilities. INT8 export of this adapter is withheld until separately validated.

FP32. Local CPU inference. No automatic desktop model switching, external skill activation, or hosted generation is part of raw inference. See Features-v0.8.md, coverage-evaluation.json, fresh-audit.json, outcome-evaluation.json and probability-evaluation.json for evidence.

The historical eight-task routing check improves6/8→7/8 covered routes, with all seven selected saved outputs passing. This reuses existing historical completions and is separate from the six fresh generations. HumanEval132 still abstains; no outcome prompt or label was fitted.
