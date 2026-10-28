# Tavi v4 code-context extension

Parent: accepted v3, preserved exactly. Additional232-fit/68-validation synthetic Python specifications train a residual four-tier softmax classifier. Only code signature/docstring contexts can use this head. Generic syntax signals and TF-IDF vocabulary use fitting examples; validation selects epoch500/gate0.55. All original arrays, skill and external-search heads remain frozen. The dataset uses neutral identifiers after a rejected naming-leakage attempt; no public benchmark prompt or label is fitted.

Coverage gains: historical7/8→8/8 and prior difficult audit4/8→6/8. Two other8-task public audits retain8/8, one assessed only after final weights froze. Two selected hosted code completions pass2/2; before/after choices match, so this is a bounded correctness check, not a task-success improvement or best-model proof.

Probability calibration uses132 fitting and132 separate check examples, including text and code contexts. It is partial: external-search calibration applies only to ordinary text; tier calibration applies only to Python specifications. Rejected combinations remain raw. Code-tier labels match22/36 (61.11%), so code predictions include a limited-validation review flag. Same-author synthetic estimates and repeated paraphrases do not establish independent field calibration or task-success probabilities. Skills remain uncalibrated scores.

FP32, CPU, original models retained for rollback. INT8 export remains withheld until this extension is separately validated. No automatic skill activation or current desktop-chat switching. See Features-v0.9.md and local JSON reports for exact evidence and limits.
