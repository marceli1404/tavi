"""Experimental dynamic activation INT8 inference with NumPy INT32 accumulation."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import platform
import statistics
import time
from tavi_model import DecisionModel, Vectorizer, sigmoid, softmax
import numpy as np


class QuantizedDecisionModel(DecisionModel):
    def __init__(self, metadata, arrays):
        super().__init__(metadata, arrays)
        for name in {'W','Wt','Ws','Wd'} | {k for k in arrays if k.endswith('_W')}:
            weights, scale = arrays[name], arrays.get(name+'_scale')
            if weights.dtype != np.int8 or weights.ndim != 2 or scale is None or scale.shape != (weights.shape[1],) or not np.all(scale>0):
                raise ValueError('Invalid INT8 matrix or column scales')

    def matmul(self, x, name):
        # Per-row dynamic activation scale, per-output-column weight scale.
        scale = np.maximum(np.max(np.abs(x), axis=1, keepdims=True)/127, 1e-12)
        qx = np.clip(np.rint(x/scale), -127, 127).astype(np.int32)
        return (qx @ self.arrays[name]).astype(np.float32)*scale*self.arrays[name+'_scale']

    def predict(self, texts):
        a = self.arrays
        x = self.vectorizer.transform(texts)
        hidden = np.tanh(self.matmul(x, 'W')+a['b'])
        tier = softmax((self.matmul(hidden, 'Wt')+a['bt'])/self.metadata.get('temperature',1))
        skills = sigmoid(self.matmul(hidden, 'Ws')+a['bs'])
        for extension in self.metadata.get('extensions', [self.metadata['extension']] if self.metadata.get('extension') else []):
            key = extension.get('array_prefix','extension')
            ev = Vectorizer(extension['vocabulary'],a[key+'_idf'])
            raw = sigmoid(self.matmul(ev.transform(texts),key+'_W')+a[key+'_b'])
            threshold = np.array(extension['thresholds'],dtype=np.float32)
            base = self.metadata['skill_threshold']
            scaled = np.where(raw <= threshold, base*raw/np.maximum(threshold,1e-8),
                              base+(1-base)*(raw-threshold)/np.maximum(1-threshold,1e-8))
            skills = np.concatenate((skills,np.where(threshold >= 1,0.,scaled)),axis=1)
        external = sigmoid(self.matmul(hidden,'Wd')+a['bd'])[:,0]
        return tier, skills, external


def export_int8(model, directory):
    if model.metadata.get('tier_adapter'):
        raise ValueError('INT8 export of the new tier adapter has not been validated; keep FP32')
    directory = Path(directory)
    if directory.exists():
        raise ValueError('Choose a new directory for the experimental INT8 model')
    matrices = {'W','Wt','Ws','Wd'} | {k for k in model.arrays if k.endswith('_W')}
    arrays = {}
    for name, value in model.arrays.items():
        if name in matrices:
            scale = np.maximum(np.max(np.abs(value),axis=0)/127,1e-12).astype(np.float32)
            arrays[name] = np.clip(np.rint(value/scale),-127,127).astype(np.int8)
            arrays[name+'_scale'] = scale
        else:
            arrays[name] = value.copy()
    metadata = copy.deepcopy(model.metadata)
    metadata.update(format='tavi-neural-int8-v1', source_weights_sha256=model.metadata['weights_sha256'],
                    quantization='symmetric per-output INT8 weights, per-row dynamic INT8 activations, INT32 accumulation; biases/idf FP32',
                    experimental=True)
    directory.mkdir(parents=True)
    np.savez_compressed(directory/'weights.npz',**arrays)
    metadata['weights_sha256'] = hashlib.sha256((directory/'weights.npz').read_bytes()).hexdigest()
    (directory/'model.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    return DecisionModel.load(directory)


def latency(model, prompts, rounds=80):
    for prompt in prompts[:8]:
        model.infer(prompt)
    elapsed = []
    for index in range(rounds):
        start = time.perf_counter_ns()
        model.infer(prompts[index%len(prompts)])
        elapsed.append((time.perf_counter_ns()-start)/1e6)
    return dict(median_ms=statistics.median(elapsed), p95_ms=float(np.percentile(elapsed,95)),
                rounds=rounds, scope='Warm batch-one infer including text features, ranking and probability summary; no process startup.')


def compare(original, quantized, prompts):
    before = original.predict(prompts)
    after = quantized.predict(prompts)
    bt,bs,bd = before
    qt,qs,qd = after
    threshold = original.metadata['skill_threshold']
    def selected(scores):
        return [set(int(i) for i in np.argsort(-row)[:3] if row[i]>=threshold) for row in scores]
    bselected,qselected = selected(bs),selected(qs)
    metrics = dict(cases=len(prompts), tier_agreement=float((bt.argmax(1)==qt.argmax(1)).mean()),
                   selected_skill_agreement=sum(a==b for a,b in zip(bselected,qselected))/len(prompts),
                   external_decision_agreement=float(((bd>=original.metadata['external_threshold']) ==
                                                     (qd>=original.metadata['external_threshold'])).mean()),
                   max_tier_score_drift=float(np.max(np.abs(bt-qt))),
                   max_skill_score_drift=float(np.max(np.abs(bs-qs))),
                   max_external_score_drift=float(np.max(np.abs(bd-qd))))
    metrics['decision_gate_passed'] = all(metrics[k] == 1 for k in ('tier_agreement','selected_skill_agreement','external_decision_agreement'))
    metrics['changed_skill_decisions'] = [dict(prompt=prompt,
        fp32=[original.metadata['skills'][i] for i in sorted(a)],
        int8=[original.metadata['skills'][i] for i in sorted(b)])
        for prompt,a,b in zip(prompts,bselected,qselected) if a != b][:40]
    return metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    original = DecisionModel.load(args.model)
    # Benchmark the same reporting path on both models; FP32 calibration is not
    # transferable to changed INT8 weights and must not skew the comparison.
    original.calibration = None
    quantized = export_int8(original,args.output)
    from training.heldout import CASES
    from training.extension_heldout import CASES as EXTENSION_CASES
    rows = json.loads((args.model/'dataset.json').read_text(encoding='utf-8'))
    probability_rows = json.loads((Path(__file__).parent/'training/probability_cases.json').read_text(encoding='utf-8'))
    prompts = list(dict.fromkeys([r['prompt'] for r in rows+probability_rows]+[r[0] for r in CASES]+[r[0] for r in EXTENSION_CASES]))
    report = dict(format='tavi-quantization-experiment-v1',source_weights_sha256=original.metadata['weights_sha256'],
                  candidate_weights_sha256=quantized.metadata['weights_sha256'],
                  comparison=compare(original,quantized,prompts),
                  frozen_acceptance_comparison=compare(original,quantized,[r[0] for r in CASES]),
                  bytes=dict(fp32_weights=(args.model/'weights.npz').stat().st_size,
                             int8_weights=(args.output/'weights.npz').stat().st_size,
                             fp32_arrays=sum(a.nbytes for a in original.arrays.values()),
                             int8_arrays=sum(a.nbytes for a in quantized.arrays.values())),
                  latency=dict(fp32=latency(original,prompts),int8=latency(quantized,prompts)),
                  environment=dict(platform=platform.platform(),numpy=np.__version__),
                  activated=False,
                  limits='One local CPU run; agreement with the original is not correctness or broad speed evidence. Feature vocabulary and Python overhead are not quantized.')
    report['recommended_default'] = 'fp32'  # Experimental export never changes the accepted pointer.
    (args.output/'quantization-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
