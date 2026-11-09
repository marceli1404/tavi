# Tavi larger-capacity research (256 hidden units)

## Goal and boundaries

Tavi's accepted v4 is a small CPU-based TF-IDF classifier with **440,817 total parameters**, including frozen tier/code/skill adapters. Its base neural network has 96 hidden units and a 4096-feature vocabulary cap. More parameters do not establish higher accuracy, better real Codex decisions or LLM-like reasoning.

This branch adds optional **real trainable capacity**, not padding or unused tensors. Wider models have trained hidden-layer weights, tier/skill/discovery heads and independently computed parameter counts. The accepted model and `models/default-model.json` remain completely unchanged.

## Reproduce one experimental candidate

Use Python 3.12+, NumPy and archived synthetic training rows. From the repository root:

```bash
python -m pip install -r requirements.txt
python -m unittest -q test_capacity_experiment
python train_tavi.py \
  --dataset models/tavi-v4-clean/dataset.json \
  --output output/capacity-256 \
  --epochs 240 \
  --hidden-size 256 \
  --vocab-limit 8192 \
  --seed 20261028
python evaluate_tavi.py --model output/capacity-256
python compare_model_capacity.py --baseline models/tavi-v4-clean \
  --candidate output/capacity-256 --output output/capacity-256/comparison.json
```

If output already exists, training refuses to overwrite it; choose a new directory. The comparator may exit 2 when validation fails and reports `retain_baseline`; that is an informative outcome, not a reason to retry until the holdout score improves.

Select from supported hidden widths 64, 96 (historical default), 128, 192, 256, 384, 512 and vocabulary caps 2048, 4096 (historical default), 8192. **The vocabulary cap is not the count**: the actual feature count is determined by the training split and recorded in the candidate's `capacity.vocabulary_size` metadata.

The CI research workflow trains one seed-locked candidate for 120 epochs and publishes a temporary GitHub Actions artifact with its weights and full reports. This is a **smoke/research run**, not a vetted or release-ready model.

## Why a larger model is not automatically better

- The existing v4 has separately trained tier and code adapters. A newly trained base MLP alone does not inherit those specialist weights, calibration or gains. Its parameter count and held-out scores must be compared with the entire accepted v4 model.
- Both the baseline's 50-case held-out evaluation and this candidate's evaluation are synthetic same-author examples. They are too small to demonstrate reliability on real Codex tasks or calibrated success probabilities.
- Use a fixed training/validation split; do not fit on acceptance cases, repeatedly sweep seeds against held-out answers or claim independent assessment.
- Real progression requires consented, privacy-safe routing outcomes, genuinely separate validation sites/task families, measured CPU inference cost and regression checks on code, installed skills and abstentions.
- The training CLI never switches the active Codex model, launches hosted work or edits `models/default-model.json`. A wider candidate is marked `experimental_capacity: true`, and `activate_candidate` refuses accidental promotion even if an old acceptance report says `passed`.

## What to review after CI

Inspect the run's `training-report.json`, `evaluation.json`, `comparison.json` and model `capacity` metadata. If synthetic accuracy is worse, retain v4 and improve training data before further scaling. If it matches or exceeds v4, do a separate real-world field evaluation before considering release. Do not report a higher parameter count as a quality improvement.
