"""Audit coding coverage with frozen old models, source arrays and disjoint cases."""
import argparse
import json
from pathlib import Path
import numpy as np
from tavi_model import DecisionModel,TIERS,is_coding_spec
from tavi_probability import signature
from training.heldout import CASES

BASE=Path(__file__).parent


def evaluate(base_dir,model_dir):
    base,model=DecisionModel.load(base_dir),DecisionModel.load(model_dir)
    suites={'original':[dict(prompt=r[0],tier=r[1]) for r in CASES],
        'development_fresh':json.loads((BASE/'training/coverage_heldout.json').read_text()),
        'prior_audit':json.loads((BASE/'training/coverage_audit.json').read_text())['cases'],
        'historical_check':[r for r in json.loads((BASE/'training/probability_cases.json').read_text()) if r['split']=='check']}
    metrics={}
    for name,rows in suites.items():
        texts=[r['prompt'] for r in rows];truth=np.array([TIERS.index(r['tier']) for r in rows])
        metrics[name]=dict(before=float((base.predict(texts)[0].argmax(1)==truth).mean()),after=float((model.predict(texts)[0].argmax(1)==truth).mean()),cases=len(rows))
    public={}
    for name,path in [('historical','humaneval/cases.json'),('development','coverage-v0.8/cases.json'),('prior_audit','coverage-v0.8/audit-cases.json'),('new_audit','coverage-v0.9/cases.json')]:
        rows=json.loads((BASE/'benchmarks'/path).read_text());rows=rows['cases'] if isinstance(rows,dict) else rows
        suites[name+'_public']=rows
        def covered(m):
            found=[]
            for r in rows:
                p=m.infer(r['prompt']);found.append(dict(task_id=r['task_id'],tier=p['tier'],covered=p['tier']!='review' and p['vocabulary_coverage']>=.15 and max(p['tier_scores'].values())>=.5))
            return found
        before,after=covered(base),covered(model)
        public[name]=dict(before=sum(r['covered'] for r in before),after=sum(r['covered'] for r in after),cases=len(rows),
            lost=sorted({r['task_id'] for r in before if r['covered']}-{r['task_id'] for r in after if r['covered']}),results=after)
    train=[]
    for filename in ('dataset.json','tier-dataset.json','coding-dataset.json'):
        train+=json.loads((Path(model_dir)/filename).read_text())
    seen={' '.join(r['prompt'].lower().split()) for r in train}
    tests=[r['prompt'] for rows in suites.values() for r in rows]
    if seen & {' '.join(p.lower().split()) for p in tests}:raise ValueError('Exact acceptance/benchmark prompt fitted')
    prompts=list(dict.fromkeys([r['prompt'] for r in train]+tests))
    a,b=base.predict(prompts),model.predict(prompts)
    arrays=all(np.array_equal(v,model.arrays[k]) for k,v in base.arrays.items())
    heads=arrays and np.array_equal(a[1],b[1]) and np.array_equal(a[2],b[2])
    noncode=[i for i,p in enumerate(prompts) if not is_coding_spec(p)]
    noncode_exact=np.array_equal(a[0][noncode],b[0][noncode])
    gates=json.loads((BASE/'training/coverage_gates_v4.json').read_text())
    passed=(metrics['original']['after']>=gates['original_tier_min'] and metrics['development_fresh']['after']>=gates['development_fresh_min']
        and metrics['prior_audit']['after']>=gates['prior_audit_min'] and metrics['historical_check']['after']>=gates['historical_check_min']
        and public['prior_audit']['after']/public['prior_audit']['cases']>=gates['known_public_audit_coverage_min']
        and public['new_audit']['after']/public['new_audit']['cases']>=gates['new_public_coverage_min']
        and all(not r['lost'] for r in public.values()) and heads and noncode_exact)
    report=dict(passed=passed,weights_sha256=model.metadata['weights_sha256'],model_signature=signature(model.metadata),metrics=metrics,public=public,
        original_arrays_skills_external_exact=heads,noncode_tier_scores_exact=noncode_exact,preservation_cases=len(prompts),noncode_cases=len(noncode),gates=gates,
        limits='Same-author policy checks and public historical coding coverage; coverage is not task success or optimal-model accuracy.')
    (Path(model_dir)/'coding-evaluation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',required=True);p.add_argument('--model',required=True);a=p.parse_args()
    r=evaluate(a.base,a.model);print(json.dumps(r,indent=2))
