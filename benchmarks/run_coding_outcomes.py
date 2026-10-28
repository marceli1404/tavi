"""Run only the two pre-fixed selected routes; no extra baseline calls when routes match."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tavi_model import DecisionModel
from tavi_probability import signature
from benchmarks.outcomes import ensure_run_manifest,generate,judge,MODEL_ROLES


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',required=True,type=Path);p.add_argument('--model',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    root=Path(__file__).resolve().parents[1]
    source=root/'benchmarks/coverage-v0.9/cases.json'
    cases=[r for r in json.loads(source.read_text()) if r['task_id'] in ('HumanEval/38','HumanEval/105')]
    models=dict(before=DecisionModel.load(a.base),after=DecisionModel.load(a.model))
    a.output.mkdir(parents=True,exist_ok=True);ensure_run_manifest(a.output,hashlib.sha256(source.read_bytes()).hexdigest())
    expected={k:signature(v.metadata) for k,v in models.items()};selection=a.output/'selection-signatures.json'
    if selection.exists() and json.loads(selection.read_text())!=expected:raise ValueError('Router changed; use a new outcome directory')
    selection.write_text(json.dumps(expected,indent=2),encoding='utf-8')
    results=[];routes={k:[] for k in models}
    for case in cases:
        if not judge(case['prompt']+case['canonical_solution'],case)['passed']:raise ValueError('Upstream reference failed')
        tiers={k:m.infer(case['prompt'])['tier'] for k,m in models.items()}
        for tier in sorted(set(tiers.values())):
            role,model,effort=next(r for r in MODEL_ROLES if r[0]==tier)
            row=generate(case,role,model,effort,a.output);results.append(row);print(json.dumps(row),flush=True)
        for key,tier in tiers.items():
            row=next(r for r in results if r['task_id']==case['task_id'] and r['role']==tier)
            routes[key].append(dict(task_id=case['task_id'],tier=tier,passed=row['verdict']['passed']))
    report=dict(requests=len(results),results=results,routes=routes,model_signatures=expected,
        scope='Two pre-fixed public tasks, one completion per unique selected route. Same before/after routes reuse the same completion; no superiority or independent real-world claim.')
    (a.model/'coding-outcomes.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('COMPLETE',json.dumps(routes),flush=True)


if __name__=='__main__':main()
