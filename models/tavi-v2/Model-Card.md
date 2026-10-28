# Tavi v2 — frozen-base skill expansion

This model adds the learned tavi-decision skill to Tavi v1. It has412153 learned parameters (408056 frozen base parameters plus4097 added classifier parameters),148 skill outputs, and uses CPU NumPy only. No pretrained model, Laya or hosted inference is needed for prediction.

## Training and architecture

The accepted base vocabulary, IDF, neural arrays, tier head, discovery head and147 existing skill heads are copied unchanged. A separate train-fitted TF-IDF vectorizer and logistic classifier learn the added label. This branch uses412 training rows and51 validation rows: the previous dataset, plus explicit synthetic Tavi-routing positives, related-task negatives and deployment metadata. Validation chooses its threshold. The dataset is saved in dataset.json with provenance; no held-out examples are imported by the trainer.

New-branch scores are threshold-normalised onto the base skill-selection scale before ranking. They are selection scores, not calibrated probabilities. Unvalidated branches produce zero selection scores and cannot be automatically activated. Stacked branches can preserve prior classifiers, but each added label still needs validation and acceptance coverage.

## Evidence

- Original50-case synthetic benchmark unchanged:96% tier accuracy,100% skill recall@3,88.2% selected precision,96.8% selected recall,16/19 no-skill accuracy and98% external classification.
- Separate20-case synthetic new-label set:8/8 Tavi-routing positives selected and12/12 related-task negatives rejected.
- All base arrays and their outputs are exactly unchanged on483 saved training/validation/acceptance prompts. This is checked independently of the headline metrics.
- Native CLI route selects tavi-decision as learned; doctor reports148 trained/148 installed and no metadata drift.
- Same-author synthetic evaluations are development evidence, not independent real-world accuracy. Baseline known failures remain; this is not a general-purpose language model or Jev-parity claim.

## Artifacts and preservation

Weights SHA256:b4c6c1c55ff09899dafc38455fbf5accdaee3e079b05d0de0b76c153b5ae8bc7.

Frozen base SHA256:22e0f8b448bee5e0fbfbfb97f9ece31291d3406e11c025679d09a5ca65206482.

training-report.json records new-head optimisation losses and validation. evaluation.json retains old-task outcomes. extension-evaluation.json records new-label cases and base preservation. Both use the exact candidate checksum. The original v1 artifact remains available; live activation also preserves the prior configuration for rollback.
