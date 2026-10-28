# Tavi v0.10 — hybrid screenshot understanding

The existing CPU router and accepted v4 clean weights are unchanged. This release adds a read-only screenshot helper for computer-use agents, publishes the v0.6–v0.9 routing improvements, and introduces a matching editable Tavi logo.

## Try it

Install the core with `python -m pip install -r requirements.txt`. Screenshot support is optional: `python -m pip install -r requirements-vision.txt`.

```sh
# Local Windows OCR only. Never sends the image to a hosted model.
python tavi.py vision screenshot.png --task "Read the screen" --mode local
# One unique exact OCR word can be located locally; ambiguous screens produce a plan.
python tavi.py vision screenshot.png --task "Locate Install" --target Install
# Authorize hosted interpretation if the local match is absent or ambiguous.
python tavi.py vision screenshot.png --task "Find the settings control" --execute
# Opt-in short-lived cache, stored on your own machine.
python tavi.py vision screenshot.png --task "Describe this screen" --execute --cache output/screens
```

The default hybrid mode uses Windows' installed OCR language models for text recognition. A unique case-insensitive exact word supplied with `--target` avoids a hosted request. Without a unique match, `--execute` authorizes Codex image inference using the existing CLI login. `--mode codex` requests hosted interpretation directly. On other platforms or when OCR is unavailable, the result says so and hybrid mode can still use Codex. This is a combination of pretrained Windows OCR and Codex vision, not a newly trained local vision language model.

Only the explicitly supplied image and task are attached by Tavi; it does not capture your desktop. Images are converted to RGB PNG, with a default maximum edge of1600 pixels. Use `--max-edge` (512–2600) when text needs more detail. Output includes prepared and original dimensions, original-coordinate candidate positions, uncertainties, and whether a hosted request actually occurred. Candidates are suggestions, never clicks. The calling computer-use agent must recheck current UI state before acting; image coordinates may differ from display coordinates due to scaling or cropping.

The optional cache contains recognized screen text and observations. Its default lifetime is300 seconds (maximum3600); `--cache-ttl 0` disables reuse. Delete your chosen cache folder when it is no longer needed. Identity includes source image bytes, dimensions, task, target, mode, model, effort, preprocessing version and response schema. Changed images or tasks cannot reuse the same entry. Unexecuted plans are never cached. Resizing can lose small details; a cache hit only establishes an identical submitted image, not that the live screen is unchanged.

## Measured smoke test

A generated1200×700 setup fixture contained a heading, an Install button and a short sentence. Windows OCR read all three and located the button text without a hosted request in752.62ms. A separate actual Codex image request correctly described the screen and located the button in5375.44ms. Repeating that same hosted request through the exact-input cache took115.67ms, with no new hosted request. Prepared PNG size was17646 bytes versus18768 original bytes. These are single local measurements, not a benchmark or a general latency guarantee; local OCR and hosted scene interpretation perform different amounts of work.

Screenshot tests cover coordinate mapping, local-only behavior, ambiguous OCR, unavailable OCR, explicit hosted authorization, cache hits and invalidation, corrupt/disabled caches, malformed responses and out-of-bounds/nonfinite coordinates. Core routing/model preservation checks remain included.

## Existing limits

The v4 coding adapter and partial synthetic calibration retain the limitations in Features-v0.9.md. Plain-text tier and code-context external-search scores remain uncalibrated. A supported bridge to switch the current desktop chat's model remains unavailable. The vision helper does not add that bridge or replace a computer-use driver. No GPU model or Ollama server is started.

CLI image-input reference: https://learn.chatgpt.com/docs/developer-commands?surface=cli
