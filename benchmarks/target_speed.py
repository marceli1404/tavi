"""Matched one-shot/warm local proposals on frozen real browser screenshots."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tavi_compact import propose
from tavi_ocr import OcrSession
from tavi_target import DEFAULT


def run(dataset,output):
    output.mkdir(parents=True,exist_ok=False)
    data=json.loads((dataset/'dataset.json').read_text(encoding='utf-8'))
    cases=[]
    for record in data['records']:
        if record['case']['split'] not in ('check','audit'): continue
        positive_targets={r['target'].casefold() for r in record['rows'] if r['label']==1}
        for label in (1,0):
            targets=sorted({r['target'].casefold() for r in record['rows'] if r['label']==label and
                            (label or r['target'].casefold() not in positive_targets)})[:2]
            for target in targets:
                cases.append(dict(image=record['case']['id']+'.png',target=target,positive=bool(label),
                    correct_boxes=[r['box'] for r in record['rows'] if r['target'].casefold()==target and r['label']==1],sha256=record['sha256']))
    manifest=dict(cases=cases,selection='First two alphabetic unique OCR targets per positive/negative class per check/audit screen. No score-based selection.',
        scope='Local screenshot preparation, fresh OCR and proposal only. Excludes agent review, physical input, UI response, interpreter startup and hosted image inference.',
        dataset_sha256=hashlib.sha256((dataset/'dataset.json').read_bytes()).hexdigest(),
        source_hashes={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in ('tavi_compact.py','tavi_target.py','tavi_actions.py','tavi_ocr.py','screen_ocr_worker.ps1')},
        target_weights_sha256=hashlib.sha256((DEFAULT/'weights.npz').read_bytes()).hexdigest())
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2))
    rows=[]
    def measure(case,method,ocr=None):
        image=dataset/case['image']
        assert hashlib.sha256(image.read_bytes()).hexdigest()==case['sha256']
        started=time.perf_counter()
        result=propose(image,'Press '+case['target'],case['target'],ocr_fn=ocr,auto_click=True)
        elapsed=(time.perf_counter()-started)*1000
        best=result['review_packet']['proposed']
        hit=bool(best and any(b[0]<=best['x']<=b[2] and b[1]<=best['y']<=b[3] for b in case['correct_boxes']))
        row=dict(image=case['image'],target=case['target'],positive=case['positive'],method=method,elapsed_ms=elapsed,
            top_target_hit=hit,eligible_correct=hit and result['eligible_compact_review'],result=result)
        rows.append(row)
        (output/'results.json').write_text(json.dumps(rows,indent=2))
        return row
    first=measure(cases[0],'one_shot_first')
    start=time.perf_counter()
    with OcrSession() as session:
        startup=(time.perf_counter()-start)*1000
        cold=measure(cases[0],'session_first',session)
        for index,case in enumerate(cases):
            methods=('one_shot','session_warm') if index%2==0 else ('session_warm','one_shot')
            pair={m:measure(case,m,session if m=='session_warm' else None) for m in methods}
            a,b=(pair[m]['result'] for m in ('one_shot','session_warm'))
            assert a['review_packet']['proposed']==b['review_packet']['proposed']
            assert a['confidence']==b['confidence'] and a['review_reasons']==b['review_reasons']
            assert a['proposal_id']!=b['proposal_id']
            assert not a['auto_click']['candidate_eligible'] and not b['auto_click']['candidate_eligible']
            assert a['hosted_calls']==b['hosted_calls']==0
            print(json.dumps(dict(index=index+1,total=len(cases),one_shot_ms=pair['one_shot']['elapsed_ms'],warm_ms=pair['session_warm']['elapsed_ms'])),flush=True)
        process=session.process
    assert process.poll() is not None
    summary={m:dict(n=len(cases),median_ms=statistics.median(r['elapsed_ms'] for r in rows if r['method']==m)) for m in ('one_shot','session_warm')}
    a,b=(summary[m]['median_ms'] for m in ('one_shot','session_warm'))
    measured=[r for r in rows if r['method']=='session_warm']
    summary.update(speedup=a/b,time_saved_percent=100*(1-b/a),worker_startup_ms=startup,first_session_total_ms=startup+cold['elapsed_ms'],
        first_one_shot_ms=first['elapsed_ms'],positive_cases=sum(r['positive'] for r in measured),
        top_target_hits=sum(r['top_target_hit'] for r in measured),eligible_correct=sum(r['eligible_correct'] for r in measured),
        automatic_candidates=0,hosted_calls=0,worker_closed=True,matching_targets_confidence_and_review_reasons=True,scope=manifest['scope'])
    (output/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('dataset',type=Path);p.add_argument('output',type=Path);a=p.parse_args();run(a.dataset,a.output)
