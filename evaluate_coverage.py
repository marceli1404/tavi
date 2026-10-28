"""Frozen policy/coverage gates for a separately fitted workload-tier adapter."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from tavi_model import DecisionModel
from tavi_probability import signature
from training.heldout import CASES

BASE=Path(__file__).parent


def evaluate(base_dir,candidate_dir):
    base_dir,candidate_dir=Path(base_dir),Path(candidate_dir)
    base,candidate=DecisionModel.load(base_dir),DecisionModel.load(candidate_dir)
    training=json.loads((candidate_dir/'tier-dataset.json').read_text())
    fresh=json.loads((BASE/'training/coverage_heldout.json').read_text())
    historical=[r for r in json.loads((BASE/'training/probability_cases.json').read_text()) if r['split']=='check']
    public=json.loads((BASE/'benchmarks/coverage-v0.8/cases.json').read_text())
    unseen=[r['prompt'] for r in fresh+historical+public]+[r[0] for r in CASES]
    normalize=lambda p:' '.join(p.lower().split())
    assert not set(map(normalize,[r['prompt'] for r in training])) & set(map(normalize,unseen)), 'Exact evaluation leakage'
    def policy(rows):
        texts=[r['prompt'] for r in rows]
        bp=base.predict(texts)[0].argmax(1)
        cp=candidate.predict(texts)[0].argmax(1)
        tiers=['fast','balanced','deep','review']
        expected=np.array([tiers.index(r['tier']) for r in rows])
        return dict(cases=len(rows),before=float((bp==expected).mean()),after=float((cp==expected).mean()))
    reports=dict(original=policy([dict(prompt=r[0],tier=r[1]) for r in CASES]),fresh=policy(fresh),historical_probability_check=policy(historical))
    def public_coverage(model):
        result=[]
        for row in public:
            p=model.infer(row['prompt'])
            covered=p['tier']!='review' and p['vocabulary_coverage']>=.15 and max(p['tier_scores'].values())>=.5
            result.append(dict(task_id=row['task_id'],covered=covered,tier=p['tier'],vocabulary_coverage=p['vocabulary_coverage']))
        return dict(coverage=sum(r['covered'] for r in result)/len(result),results=result)
    reports['public']=dict(before=public_coverage(base),after=public_coverage(candidate))
    preservation_texts=list(dict.fromkeys([r['prompt'] for r in training]+unseen))
    bp,cp=base.predict(preservation_texts),candidate.predict(preservation_texts)
    arrays_unchanged=all(k in candidate.arrays and np.array_equal(v,candidate.arrays[k]) for k,v in base.arrays.items())
    preserved=arrays_unchanged and np.array_equal(bp[1],cp[1]) and np.array_equal(bp[2],cp[2])
    gates=json.loads((BASE/'training/coverage_gates.json').read_text())
    passed=(reports['original']['after']>=gates['original_tier_accuracy_min'] and
            reports['fresh']['after']>=gates['fresh_tier_accuracy_min'] and
            reports['historical_probability_check']['after']>=gates['historical_probability_check_min'] and
            reports['public']['after']['coverage']>=gates['public_coverage_min'] and preserved)
    report=dict(weights_sha256=candidate.metadata['weights_sha256'],passed=passed,metrics=reports,
                model_signature=signature(candidate.metadata),
                frozen_heads_and_original_arrays_preserved=preserved,preservation_cases=len(preservation_texts),
                gates=gates,fresh_source_sha256=hashlib.sha256((BASE/'training/coverage_heldout.json').read_bytes()).hexdigest(),
                limitation='Policy accuracy and coverage, not task-outcome accuracy or empirical optimal-model labels.')
    (candidate_dir/'coverage-evaluation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',type=Path,required=True)
    parser.add_argument('--model',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(evaluate(args.base,args.model),indent=2))
