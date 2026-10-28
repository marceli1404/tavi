# Tavi v0.4 — incremental skill learning

## Result

The active model now learns all148 installed skill names, including tavi-decision. The original v1 model remains intact. A refreshed candidate was activated only after the old benchmark, stricter regression checks, frozen-base preservation check and separate new-label acceptance all passed.

## Behaviour

```powershell
python tavi.py doctor
python tavi.py refresh --activate
python tavi.py refresh --strategy full
python tavi.py predict "Use Tavi to choose a model and skills for this task"
python tavi.py predict "Say hello" --model-dir models/tavi-v1
```

Auto refresh uses frozen-base expansion when skill names are added and existing metadata is unchanged. Full retraining remains available for existing metadata changes or an explicit full strategy. A current catalogue returns immediately without launching training. Expansion preserves existing arrays and inference paths; it trains separate classifiers for added labels. Multiple branches are supported, but validation and acceptance coverage are required for each new label. Metadata alone does not establish readiness.

Skills without labelled validation positives get an inactive selection threshold and zero selection score. Candidates with untested new labels or altered base outputs are rejected. Original baseline gates are unchanged. Adding a new acceptance set means adding explicit cases, not labelling the new model successful merely because it has a new output neuron.

The public command defaults to the portable accepted model in models/default-model.json. Live routing may use the configured accepted candidate path; both refer to the same accepted weights in this release. No private configuration snapshots or rejected experiments are included in the ZIP.

## Verification

-412153 parameters; frozen408056-parameter base plus4097 new parameters.
- Original50-case benchmark unchanged, including16/19 no-skill outcomes.
- New20-case acceptance:8/8 positives and12/12 negatives correct.
- Base arrays and outputs unchanged across483 checked prompts.
-52 tests pass, including multi-branch preservation, invalid/uncovered skill rejection, inactive head scores, no-network inference, current-catalog no-op refresh, full-retrain forgetting rejection and corruption detection.
- Doctor reports148 learned and148 installed skills; a native route explicitly selects tavi-decision as learned.
- All evidence remains synthetic, same-author development evaluation. No independent field-accuracy, cost or Jev-parity claims.

The first experiment failed while serialising a NumPy scalar; its partial artifact was not activated. Serialisation was corrected and a fresh candidate was trained. Earlier rejected full-refresh experiments are preserved locally. No acceptance labels or baseline quality gates were weakened to accept this model.

Full retraining now retains acceptance checks for previously added skills. The earlier full-refresh candidate selected the new Tavi label on0/8 positive cases; it cannot silently replace an expanded model merely by passing old-task gates.
