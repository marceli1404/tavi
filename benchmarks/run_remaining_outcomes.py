"""Measure all three roles on the two already-known coding abstentions."""
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from benchmarks.outcomes import ensure_run_manifest,generate,judge,MODEL_ROLES
from tavi_model import DecisionModel


def main():
    root=Path(__file__).resolve().parents[1]
    source=root/'benchmarks/coverage-v0.8/audit-cases.json'
    output=root/'output/remaining-coding-outcomes-20261029'
    output.mkdir(exist_ok=False)
    cases=[r for r in json.loads(source.read_text())['cases'] if r['task_id'] in ('HumanEval/24','HumanEval/75')]
    model=DecisionModel.load(root/'models/tavi-v4-clean')
    protocol=dict(tasks=[r['task_id'] for r in cases],roles=MODEL_ROLES,requests_max=6,
                  weights_sha256=model.metadata['weights_sha256'],routes={r['task_id']:model.infer(r['prompt'])['tier'] for r in cases},
                  scope='Known abstentions; external upstream unit-test outcomes. No training, optimal-model or independent human tier labels. Historical public tasks may be memorized.')
    (output/'protocol.json').write_text(json.dumps(protocol,indent=2))
    ensure_run_manifest(output,hashlib.sha256(source.read_bytes()).hexdigest())
    results=[]
    for case in cases:
        if not judge(case['canonical_solution'],case)['passed']: raise ValueError('Reference failed')
        for role,model_name,effort in MODEL_ROLES:
            result=generate(case,role,model_name,effort,output)
            results.append(result)
            (output/'report.json').write_text(json.dumps(dict(protocol=protocol,results=results),indent=2))
            print(json.dumps(result),flush=True)


if __name__=='__main__': main()
