"""Evaluate a frozen model against separately authored synthetic acceptance cases."""
import argparse
import hashlib
import json
from pathlib import Path
import time
from training.heldout import CASES, GATES
from tavi_model import DecisionModel, TIERS
from tavi_probability import signature

BASE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, default=BASE/'models/tavi-v1')
    args = parser.parse_args()
    model = DecisionModel.load(args.model)
    rows = json.loads((args.model/'dataset.json').read_text(encoding='utf-8'))
    seen = {' '.join(r['prompt'].lower().split()) for r in rows}
    assert not any(' '.join(c[0].lower().split()) in seen for c in CASES), 'Exact test leakage'
    started = time.perf_counter()
    results = []
    for prompt, tier, skills, external in CASES:
        prediction = model.infer(prompt)
        selected = [s['name'] for s in prediction['skills'][:3] if s['score'] >= prediction['skill_threshold']]
        top3 = [s['name'] for s in prediction['skills'][:3]]
        results.append(dict(prompt=prompt, expected=dict(tier=tier, skills=skills, external=external),
                            predicted=dict(tier=prediction['tier'], skills=selected, top3=top3,
                                           external=prediction['external_score'] >= prediction['external_threshold']),
                            tier_scores=prediction['tier_scores']))
    n = len(results)
    skill_rows = [r for r in results if r['expected']['skills']]
    no_skill = [r for r in results if not r['expected']['skills']]
    metrics = dict(tier_accuracy=sum(r['predicted']['tier'] == r['expected']['tier'] for r in results)/n,
                   skill_recall_at_3=sum(bool(set(r['expected']['skills']) & set(r['predicted']['top3'])) for r in skill_rows)/len(skill_rows),
                   external_accuracy=sum(r['expected']['external'] == r['predicted']['external'] for r in results)/n,
                   no_skill_accuracy=sum(not r['predicted']['skills'] for r in no_skill)/len(no_skill),
                   majority_tier_baseline=sum(r['expected']['tier'] == 'balanced' for r in results)/n,
                   mean_inference_ms=(time.perf_counter()-started)*1000/n)
    selected_count = sum(len(r['predicted']['skills']) for r in results)
    true_positive = sum(len(set(r['expected']['skills']) & set(r['predicted']['skills'])) for r in results)
    expected_count = sum(len(r['expected']['skills']) for r in results)
    metrics['skill_precision'] = true_positive/max(selected_count, 1)
    metrics['skill_recall'] = true_positive/max(expected_count, 1)
    report = dict(scope='50 synthetic policy cases authored before training, same author as training corpus; not real-world or independent evaluation',
                  cases=n, metrics=metrics, gates=GATES,
                  passed=all(metrics[k] >= v for k, v in GATES.items()),
                  weights_sha256=model.metadata['weights_sha256'],
                  model_signature=signature(model.metadata),
                  acceptance_source_sha256=hashlib.sha256((BASE/'training/heldout.py').read_bytes()).hexdigest(),
                  results=results)
    (args.model/'evaluation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k != 'results'}, indent=2))
    print('Errors:')
    for result in results:
        if result['expected']['tier'] != result['predicted']['tier'] or (result['expected']['skills'] and not set(result['expected']['skills']) & set(result['predicted']['top3'])):
            print(json.dumps(result))


if __name__ == '__main__':
    main()
