# Screen target v1

Purpose: advisory target identification from extracted OCR candidates, spatial context and local pixel statistics. This separate CPU logistic classifier does not predict action safety, authorization or success.

Training:72 authored layouts/104 OCR candidates. Calibration:24 disjoint layouts/35 candidates. Acceptance check:24 disjoint layouts/35 candidates (18 positive,17 negative). All120 images were frozen before OCR extraction/training. Dataset and exact OCR-derived features are in training/screen-target-v1. Five images across the full corpus had no exact target extraction.

Architecture:11 input features, train-only mean/scale,11 learned coefficients plus bias. Fixed1200 Adam iterations and regularization0.006. Temperature0.5 selected only on calibration NLL, applied after calibration/check NLL and Brier gates. Check accuracy35/35;18/18 high-confidence candidates correct. Fixed proposal threshold0.9; runtime also withholds close alternatives and negative context.

Important limits: this synthetic check is simple and highly separable. Percentages are not validated for real applications. A post-training noninteractive documentation illustration scored99.9% for generic “Press Go”; Codex's compact review requested more evidence. The saved actual website heading Skip scored0.1% and was withheld. Confidence cannot replace current UI verification or host permission checks. OCR can miss controls entirely. Icons and unfamiliar styles require other evidence. See Features-v0.11.md for the full scope and audits.

The runtime checks model feature identity, weight SHA256, accepted status, array shapes/finite values, positive normalization scales and valid calibration settings. Reproduction from saved features must target a new model directory. This artifact does not change the main Tavi v4 router.
