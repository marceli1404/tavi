# Tavi v0.7 — Probability reporting and measured quantization

## Probability system

Every native prediction now includes a separate probability report: four workload-tier probabilities, external-search yes/no probabilities, normalized entropy, top-two margin, vocabulary coverage and advisory review reasons. Raw routing scores, skill thresholds and original weights remain unchanged. Skills remain uncalibrated selection scores, including the separately trained extension head.

A new64-case authored synthetic corpus was fixed before fitting:32 calibration cases and32 check cases. Exact overlap with saved train/validation and frozen base/extension acceptance prompts is rejected. Only calibration labels fit temperatures. Activation requires no check-set NLL or Brier regression on either head. Probability artifacts bind to the exact model metadata, including weight checksum; changed or quantized models cannot reuse them.

Check-set tier NLL1.7157→1.1014, Brier0.6945→0.6041, ECE0.3463→0.2379. Tier accuracy stays56.25%; probability calibration does not repair wrong class choices. External-search NLL0.2411→0.1704, Brier0.1203→0.1064, accuracy93.75%. This is small same-author synthetic policy calibration, not independent field evidence or probability of user-task success. Evidence is carried in every calibrated report. Further generalization work remains ROUTER-14.

The accepted probability.json sidecar is active for portable v2 and the existing local configured model. Original learned predictions and launch selections are preserved. Low vocabulary coverage can flag review even when a model gives an extreme score. Probability review flags are advisory and do not silently change the existing execution policy.

## INT8 experiment

The separate experimental model uses symmetric per-output-channel INT8 weights, per-row dynamic INT8 activations, INT32 accumulation, and FP32 biases/IDF. It uses actual integer dot products, not a compressed file that immediately expands to FP32. It never activates itself.

On this Windows CPU, compressed weights shrink from1534358 to280317 bytes (81.7%). Stored array buffers shrink from1681380 to446664 bytes; this is not total process memory. Vocabulary, Python overhead and temporary buffers remain.

Second controlled run with equivalent uncalibrated reporting paths,80 warm batch-one inferences per variant: FP32 median1.6921ms/p959.6840ms; INT8 median9.4340ms/p9551.0747ms. First run also found INT8 slower. This is local timing evidence, not a universal hardware benchmark.

Across597 unique saved/synthetic examples, tiers and external-search choices agree100%; selected skills agree98.995% (six differences). The frozen50-case acceptance subset agrees100% for all three decisions. The all-case exact-decision gate fails. FP32 remains the recommended and configured default. Both experimental outputs are retained; v2 includes the final comparison details. INT8 probabilities are uncalibrated because its weights differ.

Reproduce with a new output directory:

```text
python tavi_quantize.py --model models/tavi-v2 --output models/NEW_INT8_EXPERIMENT
python tavi.py predict "Say hello" --model-dir models/tavi-int8-experiment-v2
```

The report is models/tavi-int8-experiment-v2/quantization-report.json. Temperature fitting follows the held-out approach described in https://scikit-learn.org/stable/modules/calibration ; quantization error/overhead considerations are documented in https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html . No ONNX runtime or new dependency is installed in this implementation.
