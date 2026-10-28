"""Verify base preservation plus separately authored new-skill acceptance."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from tavi_model import DecisionModel
from training.extension_heldout import CASES, GATES


def evaluate(base_dir, candidate_dir, require_preservation=True):
    base_dir, candidate_dir = Path(base_dir), Path(candidate_dir)
    base, model = DecisionModel.load(base_dir), DecisionModel.load(candidate_dir)
    rows = json.loads((candidate_dir/'dataset.json').read_text(encoding='utf-8'))
    seen = {r['prompt'].strip().lower() for r in rows}
    if any(prompt.strip().lower() in seen for prompt,_ in CASES):
        raise ValueError('New-skill acceptance prompt occurs in training/validation')
    arrays_preserved = all(k in model.arrays and np.array_equal(value, model.arrays[k]) for k,value in base.arrays.items())
    prompts = [r['prompt'] for r in rows]+[p for p,_ in CASES]
    before, after = base.predict(prompts), model.predict(prompts)
    old_names = len(base.metadata['skills'])
    inherited = base.metadata.get('extensions',[base.metadata['extension']] if base.metadata.get('extension') else [])
    inherited_names = {name for branch in inherited for name in branch['names']}
    uncovered = sorted((set(model.metadata['skills'])-set(base.metadata['skills']) | inherited_names)-{'tavi-decision'})
    outputs_preserved = (np.array_equal(before[0],after[0]) and np.array_equal(before[1],after[1][:,:old_names])
                         and np.array_equal(before[2],after[2]))
    results = []
    for prompt, expected in CASES:
        prediction = model.infer(prompt)
        selected = [s['name'] for s in prediction['skills'][:3] if s['score'] >= prediction['skill_threshold']]
        results.append(dict(prompt=prompt, expected=expected, selected='tavi-decision' in selected,
                            selected_skills=selected))
    tp = sum(r['selected'] and r['expected'] for r in results)
    fp = sum(r['selected'] and not r['expected'] for r in results)
    positives = sum(r['expected'] for r in results)
    negatives = len(results)-positives
    metrics = dict(recall=tp/max(positives,1), precision=tp/max(tp+fp,1), specificity=(negatives-fp)/max(negatives,1))
    report = dict(scope='Same-author synthetic new-skill cases fixed before expansion training; not independent field evaluation',
                  weights_sha256=model.metadata['weights_sha256'], base_weights_sha256=base.metadata['weights_sha256'],
                  arrays_preserved=arrays_preserved, outputs_preserved=outputs_preserved,
                  preservation_required=require_preservation,
                  uncovered_new_skills=uncovered,
                  preservation_prompts=len(prompts), metrics=metrics, gates=GATES,
                  passed=not uncovered and (not require_preservation or (arrays_preserved and outputs_preserved)) and all(metrics[k]>=v for k,v in GATES.items()),
                  acceptance_source_sha256=hashlib.sha256(Path(__file__).with_name('training').joinpath('extension_heldout.py').read_bytes()).hexdigest(),
                  results=results)
    (candidate_dir/'extension-evaluation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',type=Path,required=True)
    parser.add_argument('--model',type=Path,required=True)
    parser.add_argument('--allow-base-change',action='store_true',help='For full retraining: retain new-label gates but do not require frozen arrays')
    args = parser.parse_args()
    result = evaluate(args.base,args.model,not args.allow_base_change)
    print(json.dumps({k:v for k,v in result.items() if k != 'results'},indent=2))
