# Tavi v0.12 — warm local OCR sessions

Repeated screenshot-to-proposal work can now keep Windows OCR loaded instead of starting PowerShell and initializing recognition for every image. The session processes each supplied screenshot again, then creates a fresh target proposal for the current Codex agent to review. It reuses the recognition engine, not a result or authorization.

## Use during computer work

Start one process with stdin kept open:

```sh
python tavi.py propose-stream
```

After its ready response, send one JSON object per line for each fresh capture:

```json
{"id":"step-1","image":"C:/captures/current.png","task":"Press Go","target":"Go"}
```

Each response includes the request ID, fresh proposal ID, submitted-image hash, local target-match estimate, nearby OCR context and candidate coordinates. Review it in the current Codex chat, verify the current UI and coordinate mapping with the supported computer-use driver, act within the user request, then check the result. Prefer DOM/accessibility data when it already identifies the control.

The stream accepts only image, task, target, optional id and max_edge fields. It cannot enable a hosted review, image upload or input action. Close stdin or interrupt the process when work ends; its owned OCR worker exits. No service, listening port, GPU model or background startup entry is installed. A worker failure/timeout closes the session rather than returning an earlier result. One bad image is reported without reusing previous observations.

Python callers can use `with OcrSession() as ocr:` from tavi_ocr and pass `ocr_fn=ocr` to `propose`. The existing one-shot `propose` command remains available. One screenshot still pays startup costs; the speed benefit is repeated work within a session.

## Measured result

A matched CPU comparison used12 different1200×700 synthetic screenshots with changing target words, colors and positions. Each image was processed once by the one-shot path and once by the warm session, alternating pair order. There was no Tavi image-result cache, hosted request, click or keyboard action. Both paths used the same target model, confidence computation and proposal checks.

| Local stage | Median | Range | Cases |
|---|---:|---:|---:|
| One-shot screenshot to proposal | 468.065ms | 460.577–492.650ms | 12 |
| Warm-session screenshot to proposal | 60.848ms | 56.977–66.906ms | 12 |

This is7.69× as fast, or87.00% less local processing time. Both paths found12/12 correct targets, with matching confidence values and positions within one pixel. Their proposal IDs differed, and all13 generated fixture image hashes were distinct (one warmup plus12 measured cases).

Worker startup took311.247ms; its first proposal took another166.712ms, giving477.959ms total. The first one-shot proposal took515.856ms. These are single-machine smoke-test timings. Python interpreter startup was excluded equally, and the warmup is separated from steady-state measurements. No full Computer Use driver, current-chat reasoning, UI response or action-completion speed was measured. Built-in Computer Use output and controls are unchanged.

Exact protocol, images, raw timings and summary are retained in output/ocr-session-optimization-v2. The earlier preliminary run is preserved separately. A real streaming CLI check processed two changing images, including a filename with Unicode and apostrophes, returned new hashes/IDs, sent no hosted requests, and exited at EOF. Direct session checks confirm the owned worker terminates on closure.

## Preserve useful rejection behavior

The v0.11 documentation illustration could receive99.9% synthetic target confidence. The runtime now withholds proposals when nearby OCR explicitly says “illustration only,” “not an interactive,” “not interactive” or “example only.” The original illustration is withheld locally with no hosted review.

This is a narrow, visible context rule, not improved model calibration or proof that all noninteractive content is detected. Target percentages remain synthetic estimates, never action-safety/authorization probabilities. Disabled, ambiguous, missing-target, changed-input and stale-review checks remain in force. Main router and target-model weights are unchanged; independent real-screen calibration remains future work.

Tests cover session protocol correlation, failed initialization, invalid/mismatched responses, timeout, process closure, fresh requests after unreadable images, stream-local-only restrictions, malformed/oversized input, Unicode filenames and the noninteractive context regression. The complete source suite also retains routing, model preservation and outcome replay checks.
