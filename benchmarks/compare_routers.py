"""Compare frozen Tavi and warm CPU Laya against measured coding outcomes."""
import argparse
import json
from pathlib import Path
import queue
import shutil
import statistics
import subprocess
import sys
import threading
import time

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
from tavi_model import DecisionModel
from tavi_health import model_location
from benchmarks.outcomes import MODEL_ROLES


class WarmLaya:
    def __init__(self,runner):
        started=time.perf_counter()
        self.process=subprocess.Popen([shutil.which('node') or 'node',str(BASE/'benchmarks/laya_worker.mjs'),runner],
                                      stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                      text=True,encoding='utf-8',bufsize=1)
        self.queue=queue.Queue()
        def reader():
            for line in self.process.stdout:
                try:self.queue.put(json.loads(line))
                except ValueError:pass
            self.queue.put(None)
        threading.Thread(target=reader,daemon=True).start()
        threading.Thread(target=lambda:list(self.process.stderr),daemon=True).start()
        ready=self.queue.get(timeout=60)
        if not ready or not ready.get('ready'):
            self.close()
            raise RuntimeError('Persistent Laya CPU worker failed to initialise')
        self.startup_seconds=time.perf_counter()-started

    def decide(self,prompt):
        request=dict(id=1,state={'task':prompt},questions={'tier':dict(type='choice',
          instructions='Choose a workload tier for this coding task. Prefer the efficient tier when the task is straightforward.',
          criteria={'fast':'Simple well-specified coding, transformations or explanations',
                    'balanced':'Ordinary implementation, debugging or analysis',
                    'deep':'Difficult proofs, subtle concurrency or complex architecture',
                    'review':'Task is too ambiguous to choose'})})
        self.process.stdin.write(json.dumps(request)+'\n');self.process.stdin.flush()
        response=self.queue.get(timeout=60)
        if not response or response.get('error'):
            raise RuntimeError('Laya inference failed')
        answer=response['result']['answers']['tier']
        chosen=answer['choice']
        score=answer['probabilities'][chosen]
        return dict(raw_tier=chosen,tier=chosen if score>=.5 and chosen!='review' else 'review',
                    tier_scores=answer['probabilities'],inference_ms=response['elapsed_ms'])

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=5)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--outcomes',type=Path,default=BASE/'output/outcome-benchmark/report.json')
    parser.add_argument('--output',type=Path,default=BASE/'output/outcome-benchmark/router-comparison.json')
    args=parser.parse_args()
    config_path=BASE/'tavi.config.json'
    config=json.loads(config_path.read_text(encoding='utf-8-sig'))
    cases=json.loads((BASE/'benchmarks/humaneval/cases.json').read_text(encoding='utf-8'))
    model=DecisionModel.load(model_location(config,config_path,BASE))
    outcomes=json.loads(args.outcomes.read_text(encoding='utf-8'))
    matrix={(r['task_id'],r['role']):r for r in outcomes['results']}
    missing=[(c['task_id'],role) for c in cases for role,_,_ in MODEL_ROLES if (c['task_id'],role) not in matrix]
    if missing:
        raise ValueError('Outcome matrix is incomplete; finish the bounded8-case run before comparison')
    results=[]
    worker=WarmLaya(config['laya_runner'])
    try:
        # Untimed warm-up for both models; cold startup is reported separately.
        model.infer('Implement a simple Python function')
        worker.decide('Implement a simple Python function')
        for case in cases:
            prompt=case['prompt']
            start=time.perf_counter()
            prediction=model.infer(prompt)
            elapsed=(time.perf_counter()-start)*1000
            tier=prediction['tier'] if max(prediction['tier_scores'].values())>=.5 and prediction['vocabulary_coverage']>=.15 else 'review'
            tavi=dict(raw_tier=prediction['tier'],tier=tier,tier_scores=prediction['tier_scores'],inference_ms=elapsed)
            laya=worker.decide(prompt)
            entry=dict(task_id=case['task_id'],tavi=tavi,laya=laya)
            for name in ('tavi','laya'):
                selected=entry[name]['tier']
                observed=matrix.get((case['task_id'],selected))
                entry[name]['observed_outcome']=observed
            results.append(entry)
            print(json.dumps(entry),flush=True)
    finally:worker.close()
    summary={}
    for name in ('tavi','laya'):
        rows=[r[name] for r in results]
        covered=[r for r in rows if r['observed_outcome']]
        summary[name]=dict(tasks=len(rows),covered=len(covered),abstained=sum(r['tier']=='review' for r in rows),
                           passed=sum(r['observed_outcome']['verdict']['passed'] for r in covered),
                           median_local_inference_ms=statistics.median(r['inference_ms'] for r in rows),
                           selected_generation_seconds=sum(r['observed_outcome']['elapsed_seconds'] for r in covered),
                           selected_input_tokens=sum((r['observed_outcome'].get('usage') or {}).get('input_tokens',0) for r in covered),
                           selected_output_tokens=sum((r['observed_outcome'].get('usage') or {}).get('output_tokens',0) for r in covered))
    report=dict(scope='Observed results for8 pinned public coding tasks; one generation per role/task. Local router confidence is not cross-model calibrated; abstentions reported separately.',
                model_weights_sha256=model.metadata['weights_sha256'],laya_startup_seconds=worker.startup_seconds,
                summary=summary,common_coverage=common_coverage(results),results=results,usd_cost=None,
                method='Router decisions replayed against one measured outcome matrix; no duplicate hosted requests. Laya uses the published four-choice tier prompt; both routers use0.5 score cutoff, not cross-model calibrated confidence.',
                limits=['Small historical dataset; possible foundation-model memorisation','Not a real-world coding-project benchmark',
                        'No task-level model oracle labels used for training','No dollar-price or statistically significant superiority claim'])
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
def common_coverage(results):
    shared=[r for r in results if all(r[name].get('observed_outcome') for name in ('tavi','laya'))]
    comparison={'tasks':len(shared),'task_ids':[r['task_id'] for r in shared]}
    for name in ('tavi','laya'):
        selected=[r[name]['observed_outcome'] for r in shared]
        comparison[name]=dict(passed=sum(r['verdict']['passed'] for r in selected),
                              generation_seconds=sum(r['elapsed_seconds'] for r in selected),
                              local_router_ms=sum(r[name]['inference_ms'] for r in shared),
                              input_tokens=sum((r.get('usage') or {}).get('input_tokens',0) for r in selected),
                              output_tokens=sum((r.get('usage') or {}).get('output_tokens',0) for r in selected))
    return comparison


