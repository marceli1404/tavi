# Tavi v0.14 — real-screen audit and confidence qualification

ROUTER-20 and ROUTER-25 have new evidence, but their broad reliability goals remain open. Accepted router and target weights are unchanged. A rejected target candidate is retained locally for inspection and is not activated or bundled.

## Real-screen target audit

Before collection, a protocol fixed eight public sites, three widths and site-disjoint train/calibration/check/audit partitions. The 24 screenshots have labels from visible browser DOM roles, enabled state and rectangles, independently of Tavi predictions. Screenshot dimensions differ from DOM viewport dimensions; labels map both axes into image coordinates. The initial unmapped extraction was invalid and is retained separately, excluded from all reported results.

Actual Windows OCR produced 1,100 unique candidate observations: 468 training, 256 calibration, 309 check and67 additional audit observations. Case-insensitive target/candidate identities were deduplicated. The raw request audit had1,225 observations, including repeated case variants; its19 high-confidence failures reduce to16 unique failures. These are clustered observations from eight sites, not1,100 independent user tasks. A candidate is positive when its center lies inside an enabled visible button. Links, headings and selectors are negatives under this button-specific contract. Exact-word OCR can miss controls entirely; candidate counts do not measure end-to-end recall.

On the two untouched check sites, the existing synthetic model assigned at least95% to16 unique candidates; none were actual button targets. The separate audit site had no95% predictions. A logistic replacement fitted only training sites improved check Brier loss from0.08286 to0.03066, but produced no high-confidence coverage and failed the existing acceptance gate. Its temperature calibration also failed a non-regression check. The candidate is rejected; higher majority-class accuracy is not evidence of useful button recognition.

`models/screen-target-v1/field-evaluation.json` records the failed audit, dataset hash and exact target-weight hash. Loading an audit for different weights, an unsupported status or a claimed automatic qualification fails closed. Removing the audit does not restore qualification.

## Automatic actions

The owner's local automatic-button setting remains enabled with the raw95% threshold. However, a proposal must now also carry `confidence.automatic_probability_qualified=true`. The current screenshot model cannot supply that qualification. Its proposals retain the compact Codex/agent review path and explicitly report failed field validation. A synthetic99.9% score cannot become an automatic-click candidate.

This correction supersedes the v0.13 example in which the synthetic Go fixture qualified automatically. Host verification, permissions, freshness, exact task/target/image bindings and single-attempt handling remain required. A host's own independently verified UI action can still proceed within the user request; this change only withholds Tavi's unsupported probability-based automatic eligibility.

## Coding outcomes

The two remaining difficult-audit abstentions were HumanEval/24 and HumanEval/75. Each received one completion from fast, balanced and deep roles, six hosted requests total. All six passed the upstream external unit tests. Across these two tasks, median measured generation times were4.56s fast,6.81s balanced and9.30s deep. These are small historical public tests, potentially memorized by hosted models, with uncontrolled service variation.

No evaluation prompt was added to training, no confidence gate was lowered and no raw success rate was presented as calibrated optimal-model probability. The router still abstains on those two tasks. Code-context synthetic tier agreement remains22/36; missing calibration contexts remain uncalibrated. An explicit model selection remains available when the user or agent can resolve a review.

## Matched real-screen speed test

Thirty requests used nine frozen check/audit screenshots. Selection took the first two alphabetic, case-insensitive positive and negative OCR target words per screen, excluding positive words from the negative-only class, without looking at model scores. Twelve requests had an actual button candidate. Pair order alternated between one-shot and warm-session OCR, with fresh recognition and unique proposals each time.

Median local preparation/OCR/proposal time was549.52ms one-shot and139.70ms with a warm session:3.93x as fast,74.58% less time. First-session startup plus first proposal was594.12ms; first one-shot was685.04ms. Targets, confidence and review reasons matched across both methods. The worker closed after the test; no image upload, hosted review or input action occurred.

Only5/12 positive requests ranked a true button first, and none qualified for compact acceptance because confidence/context gates withheld them. Automatic eligibility was zero. This is a local processing speed improvement, not demonstrated faster successful full computer use. Agent review, physical input, UI response and direct hosted image inference were not timed.

## Evidence and remaining work

Local evidence is under `output/field-target-20261029/deduplicated`, `output/remaining-coding-outcomes-20261029` and `output/field-speed-20261029-qualified`. Raw site screenshots and OCR context are kept local; the portable archive includes aggregate reports only. The source includes audit and timing runners for new explicitly collected datasets. Full automatic target confidence still needs richer independent positive/control labels and successful untouched evaluation. Independent field outcomes and optimal-model routing labels remain outstanding. No GPU use, website edit, deployment or GitHub publication is part of this update.
