# Tavi v0.11 — target percentages and compact Codex review

Tavi can now identify an OCR target locally, attach a learned target-match estimate, and return a small text proposal to the current Codex chat. The agent reviews the proposed target, then uses its supported computer-use tools within the user's request and verifies the result. Tavi itself does not click or expand the host's action permissions.

```sh
python tavi.py propose screenshot.png --task "Press Go to open the preview" --target Go
```

The result includes a question for Codex, proposed label and coordinates, nearby OCR text, alternatives, confidence scope, a unique proposal ID and the submitted image hash. It sends no image or hosted request by default. This lets the current Codex agent review the compact evidence without starting a second conversation. Prefer DOM/accessibility data when the computer-use driver already exposes it.

For a headless workflow, an explicit `--execute` requests a separate text-only Codex review:

```sh
python tavi.py propose screenshot.png --task "Press Go" --target Go --execute
```

Codex returns `proceed`, `reject` or `need_image`, bound to the exact proposal ID and candidate. It cannot substitute coordinates. Review runs in a separate temporary working folder containing no screenshot, and no image flag/path is provided. Unexpected reviewer tool use is rejected. Reviews are never cached as permission to act. The host must recheck the live UI and image/display coordinate mapping after reviewing, act within the existing user request and its permissions, and verify the outcome.

Missing words, low confidence, close competing candidates or negative context produce a request for image review instead of a confident proposal. No full image is silently sent. Add `--allow-image-fallback --execute` only when that image request is intended. Fallback returns image observations for host review; it does not approve an action automatically. `vision --mode codex` remains available for direct scene interpretation.

## What the percentage means

The separate CPU logistic model estimates whether an extracted OCR candidate matches the intended control in authored synthetic layouts. It does **not** estimate whether pressing the control is safe, authorized, enabled or guaranteed to succeed. Its output explicitly says `field_validated: false`. Displayed estimates are capped at99.9% to avoid rounding them into a100% guarantee.

The corpus contains120 generated UI images:72 training,24 calibration and24 check layouts, with disjoint seeds and image hashes. Layouts vary position, font size, color, target word, duplicate-label context, prose distractors and disabled controls. Actual Windows OCR produced104 training candidates,35 calibration candidates and35 check candidates. Five layouts across the complete corpus produced no exact OCR target. Ground-truth rendered control rectangles provide labels; no field click outcomes were collected.

The model has11 features and12 trained logistic parameters, with train-only normalization and a temperature selected from calibration labels. The applied temperature0.5 improves check NLL0.01404→0.000252 and Brier0.000242→0.000000129. All35 check candidates were classified correctly, including18 high-confidence positives. This is an easy, small, same-author synthetic check, not evidence of99.9% real-world reliability. The held-out check was used only for acceptance/calibration gates; it did not choose training weights or temperature. Fitted arrays, the model card, exact corpus, OCR records and evaluation are retained for reproduction.

An additional post-training documentation illustration exposed a high-confidence mistake: for the generic task “Press Go,” the model displayed99.9% despite the label belonging to an illustration. The actual text-only Codex reviewer returned `need_image` after reading the nearby “Illustration only. Not an interactive” text. No image was sent and no action occurred. On the saved live website screenshot, the noninteractive “Skip” heading received0.1% and was withheld locally. These audits are retained and show why local confidence is advisory.

## Measured behavior

Three local proposal preparations on a new Go-button fixture had a median471.528ms. Three separate text-only reviews including local preparation had a median4542.312ms; three regular image requests had a median4074.790ms. Every measured target was correct. One independent rejection check overlapped the first pair, so these small timings are illustrative and do not establish a general latency difference. The two later pairs also showed no separate-call speed improvement.

The default current-chat proposal avoids a second hosted call and sends zero image bytes. Its local preparation time excludes the current agent's own review and input-action time. The headless extra review was slower in this sample despite carrying a much smaller payload. Smaller input alone does not establish lower end-to-end latency. See `output/compact-review-check` for the frozen fixture, comparison protocol, raw observations and timing summary. Earlier v0.10 benchmark results remain separate.

## Reproduce

Core dependencies remain NumPy. Screenshot features require `requirements-vision.txt`. Extraction uses Windows OCR and the training renderer uses Windows Arial. Training from the portable recorded feature corpus needs only NumPy:

```sh
python train_screen_target.py training/screen-target-v1 --train models/screen-target-reproduction
python -m unittest -q
```

The destination must be new. `train_screen_target.py NEW_DATA_DIRECTORY --prepare --extract --train NEW_MODEL_DIRECTORY` generates and freezes a new corpus, runs actual OCR and trains a separate candidate. Gates must pass before the runtime loads it. The accepted v4 main routing weights and their calibration remain unchanged; this is an additional target-confidence model.

Official structured-output reference: https://learn.chatgpt.com/docs/non-interactive-mode
