# Screenshot preparation in v0.24

Compact target proposals now reuse prepared RGB pixels for target features and
image fallback. When image fallback is enabled, local OCR reads a temporary
uncompressed BMP; Tavi creates a compressed PNG only when an image review is
actually requested. With fallback disabled, local OCR keeps the fast PNG path.
Local temporary bitmaps use more disk space than compressed PNGs.

The screenshot hash and preparation share one captured byte sequence. The final
source-change check remains. Retained pixel buffers are closed after use.
Targets, coordinates, confidence calculations, field-qualification checks and
action permissions are unchanged. This does not qualify automatic clicks.

In 120 alternating paired local tests on two saved synthetic fixtures, proposal
processing fell from 31.82 to 13.74 ms and from 110.55 to 71.08 ms. Scripted text
review fell from 31.19 to 13.84 ms and from 113.53 to 75.85 ms. Image fallback
was mixed: 37.88 to 40.36 ms and 130.77 to 127.42 ms. Six additional native
Windows OCR comparisons preserved proposal results and uploaded image pixels.

Timings used scripted OCR/review callbacks while CPU training ran in the
background. They exclude actual OCR latency, screen capture, agent reasoning,
hosted inference, transport, live-state checks, clicks and app response. These
small local measurements do not establish a whole-computer-use speedup or field
accuracy. Native OCR comparisons establish parity, not action success. See the
[raw local timing summary](benchmarks/compact-preparation-v0.24/report.json).

Earlier fast-PNG and BMP-only attempts improved no-image work but added more
fallback overhead; they were refined by reusing decoded pixels. No best-run
selection, new confidence calibration or full-agent speed claim is implied.

Nine focused regression tests cover lazy compression, decoded pixels, exact
sent-byte accounting, RGB/alpha/grayscale/EXIF inputs, thumbnail coordinates,
source swaps, retained-buffer cleanup and unchanged review/action guards.
Accepted model weights and the default model pointer are unchanged.
