"""Three-way frozen-screenshot local proposal benchmark; no hosted calls or inputs."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
import sys
import time
from unittest.mock import patch
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
import tavi_compact
import tavi_target
from tavi_ocr import OcrSession


def load(path,name,sha):
    assert hashlib.sha256(path.read_bytes()).hexdigest()==sha
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def run(dataset,baseline,output,cases_manifest=None,verify_case_inputs=False):
    output.mkdir(exist_ok=False)
    old_target=load(baseline/'tavi_target.py','old_target','abe870f5a1888adbbe4b77e3cdf803e17f8705f88d862662ff80eb71c7d0f8c4')
    old_vision=load(baseline/'tavi_vision.py','old_vision','a699d9126c93b528f47111341c099ab88bb67bf90609e2f9ef959aeb98288116')
    data=json.loads((dataset/'dataset.json').read_text())
    cases=[]
    for record in data['records']:
        for task,target in sorted({(r['task'],r['target']) for r in record['rows']})[:2]:
            boxes=[r['box'] for r in record['rows'] if r['target']==target and r['label']==1]
            cases.append(dict(image=record['case']['id']+'.png',task=task,target=target,
                              sha256=record['sha256'],correct_boxes=boxes))
    seed='tavi-proposal-pipeline-v017'
    cases=sorted(cases,key=lambda c:hashlib.sha256((seed+c['image']+c['task']+c['target']).encode()).hexdigest())[:30]
    selection='SHA256-ranked first30 of first two alphabetic task/target pairs per screenshot; no score/timing selection.'
    metadata_note=None
    if cases_manifest is not None:
        frozen=json.loads(cases_manifest.read_text())
        current_sha=hashlib.sha256((dataset/'dataset.json').read_bytes()).hexdigest()
        if current_sha!=frozen['dataset_sha256']:
            if not verify_case_inputs:raise ValueError('Dataset metadata changed; verify exact frozen image/task/box inputs explicitly')
            current_records={r['case']['id']+'.png':r for r in data['records']}
            for case in frozen['cases']:
                assert hashlib.sha256((dataset/case['image']).read_bytes()).hexdigest()==case['sha256']
                boxes=[r['box'] for r in current_records[case['image']]['rows'] if r['target'].casefold()==case['target'].casefold() and r['label']==1]
                assert sorted(boxes)==sorted(case['correct_boxes'])
            metadata_note=dict(historical_dataset_sha256=frozen['dataset_sha256'],current_dataset_sha256=current_sha,
                verification='Every used screenshot SHA256 and all frozen target boxes agree with current records. Task/target/boxes taken verbatim from frozen manifest; unrelated metadata is not an inference input.')
        cases=[dict(**case,task='Press '+case['target']) for case in frozen['cases']]
        assert len(cases)==30
        selection='Reuse the exact historical30-case field-speed qualified manifest, including12 positive control requests; no timing/score selection.'
    methods=['v016_one_shot','v016_warm','optimized_warm']
    manifest=dict(cases=cases,selection=selection,
        metadata_verification=metadata_note,
        cases_manifest_sha256=hashlib.sha256(cases_manifest.read_bytes()).hexdigest() if cases_manifest else None,
        seed=seed,methods=methods,order='Rotate the three methods by case index; each position occurs10times.',
        dataset_sha256=hashlib.sha256((dataset/'dataset.json').read_bytes()).hexdigest(),
        source_hashes={name:hashlib.sha256((BASE/name).read_bytes()).hexdigest() for name in ['tavi_compact.py','tavi_target.py','tavi_vision.py','tavi_ocr.py','tavi_actions.py','screen_ocr.ps1','screen_ocr_worker.ps1']},
        baseline_hashes={name:hashlib.sha256((baseline/name).read_bytes()).hexdigest() for name in ['tavi_target.py','tavi_vision.py']},
        target_weights_sha256=hashlib.sha256((tavi_target.DEFAULT/'weights.npz').read_bytes()).hexdigest(),
        scope='Complete local source hash/preparation/PNG/OCR/target proposal/qualification planning. Excludes interpreter startup, host capture, agent review, input, UI response and hosted inference. Saved screenshots do not establish live state.')
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    def legacy_prepare(path,destination,max_edge,**options):return old_vision.prepare(path,destination,max_edge)
    new_prepare=tavi_compact.prepare
    rows=[]
    start=time.perf_counter()
    with OcrSession() as session:
        startup=(time.perf_counter()-start)*1000
        tavi_compact.propose(dataset/cases[0]['image'],cases[0]['task'],cases[0]['target'],ocr_fn=session)
        for index,case in enumerate(cases):
            image=dataset/case['image'];assert hashlib.sha256(image.read_bytes()).hexdigest()==case['sha256']
            results={}
            for method in methods[index%3:]+methods[:index%3]:
                optimized=method=='optimized_warm'
                with patch.object(tavi_compact,'candidates',tavi_target.candidates if optimized else old_target.candidates),patch.object(tavi_compact,'prepare',new_prepare if optimized else legacy_prepare):
                    start=time.perf_counter()
                    result=tavi_compact.propose(image,case['task'],case['target'],ocr_fn=None if method=='v016_one_shot' else session,auto_click=True)
                    elapsed=(time.perf_counter()-start)*1000
                assert result['hosted_calls']==0 and not result['auto_click']['candidate_eligible']
                proposed=result['review_packet']['proposed']
                hit=bool(proposed and any(b[0]<=proposed['x']<=b[2] and b[1]<=proposed['y']<=b[3] for b in case['correct_boxes']))
                results[method]=result
                rows.append(dict(case=index,image=case['image'],target=case['target'],method=method,ms=elapsed,
                    positive=bool(case['correct_boxes']),top_target_hit=hit,proposal_id=result['proposal_id']))
            reference=results['v016_one_shot']
            for result in results.values():
                assert result['review_packet']['proposed']==reference['review_packet']['proposed']
                assert result['confidence']==reference['confidence'] and result['review_reasons']==reference['review_reasons']
            assert len({r['proposal_id'] for r in results.values()})==3
            (output/'results.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
            print(json.dumps(dict(paired_cases=index+1,total=len(cases))),flush=True)
        worker=session.process
    assert worker.poll() is not None
    summary={method:dict(n=len(cases),median_ms=statistics.median(r['ms'] for r in rows if r['method']==method),
                         positive_cases=sum(r['positive'] for r in rows if r['method']==method),
                         top_target_hits=sum(r['top_target_hit'] for r in rows if r['method']==method)) for method in methods}
    result=dict(methods=summary,speedup_vs_one_shot=summary['v016_one_shot']['median_ms']/summary['optimized_warm']['median_ms'],
                speedup_vs_previous_warm=summary['v016_warm']['median_ms']/summary['optimized_warm']['median_ms'],
                time_saved_vs_previous_warm_percent=100*(1-summary['optimized_warm']['median_ms']/summary['v016_warm']['median_ms']),
                worker_startup_ms=startup,worker_closed=True,targets_confidence_review_reasons_exact=True,
                automatic_candidates=0,hosted_calls=0,scope=manifest['scope'])
    (output/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('dataset',type=Path);p.add_argument('baseline',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--cases-manifest',type=Path)
    p.add_argument('--verify-case-inputs',action='store_true')
    a=p.parse_args();run(a.dataset,a.baseline,a.output,a.cases_manifest,a.verify_case_inputs)
