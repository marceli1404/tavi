"""Compare sampled-pixel features with the immutable public v0.16 implementation."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
import sys
import time
import tracemalloc
from unittest.mock import patch
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
import tavi_target
import tavi_compact
from tavi_ocr import OcrSession

BASELINE_SHA='abe870f5a1888adbbe4b77e3cdf803e17f8705f88d862662ff80eb71c7d0f8c4'
BASELINE_VISION_SHA='a699d9126c93b528f47111341c099ab88bb67bf90609e2f9ef959aeb98288116'


def run(dataset,baseline,output):
    output.mkdir(exist_ok=False)
    assert hashlib.sha256(baseline.read_bytes()).hexdigest()==BASELINE_SHA
    spec=importlib.util.spec_from_file_location('frozen_target_v016',baseline)
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    vision_source=baseline.with_name('tavi_vision.py')
    assert hashlib.sha256(vision_source.read_bytes()).hexdigest()==BASELINE_VISION_SHA
    spec=importlib.util.spec_from_file_location('frozen_vision_v016',vision_source)
    old_vision=importlib.util.module_from_spec(spec);spec.loader.exec_module(old_vision)
    records=json.loads((dataset/'dataset.json').read_text(encoding='utf-8'))['records']
    cases=[]
    for record in records:
        for task,target in sorted({(r['task'],r['target']) for r in record['rows']})[:2]:
            cases.append(dict(image=record['case']['id']+'.png',task=task,target=target,
                              sha256=record['sha256'],ocr=record['ocr'],pixels=record['image_size'][0]*record['image_size'][1]))
    manifest=dict(baseline_source_sha256=BASELINE_SHA,
        baseline_vision_sha256=BASELINE_VISION_SHA,
        candidate_source_sha256=hashlib.sha256((BASE/'tavi_target.py').read_bytes()).hexdigest(),
        candidate_vision_sha256=hashlib.sha256((BASE/'tavi_vision.py').read_bytes()).hexdigest(),
        candidate_compact_sha256=hashlib.sha256((BASE/'tavi_compact.py').read_bytes()).hexdigest(),
        dataset_sha256=hashlib.sha256((dataset/'dataset.json').read_bytes()).hexdigest(),
        selection='First two alphabetic task/target pairs from every recorded screenshot; no score/label selection.',
        feature_repeats=5,proposal_case_indexes=list(range(0,len(cases),4)),
        cases=[{k:v for k,v in c.items() if k!='ocr'} for c in cases],
        limits='Saved real screenshots, not fresh UI state. No agent review, clicks or app-response timing; accuracy unchanged only if differential checks pass.')
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    functions={'baseline':old.candidates,'optimized':tavi_target.candidates}
    def legacy_prepare(image,destination,max_edge,**options):
        return old_vision.prepare(image,destination,max_edge)
    preparers={'baseline':legacy_prepare,'optimized':tavi_compact.prepare}
    timings={name:[] for name in functions};rows=[]
    for index,case in enumerate(cases):
        image=dataset/case['image']
        assert hashlib.sha256(image.read_bytes()).hexdigest()==case['sha256']
        expected=old.candidates(image,case['ocr'],case['task'],case['target'])
        actual=tavi_target.candidates(image,case['ocr'],case['task'],case['target'])
        assert expected==actual,case['image']
        for repeat in range(5):
            for name in (('baseline','optimized') if (index+repeat)%2==0 else ('optimized','baseline')):
                start=time.perf_counter();result=functions[name](image,case['ocr'],case['task'],case['target'])
                ms=(time.perf_counter()-start)*1000
                assert result==expected
                timings[name].append(ms)
                rows.append(dict(case=index,repeat=repeat,method=name,ms=ms,candidates=len(result)))
        if index%12==11: print(json.dumps(dict(feature_cases_verified=index+1,total=len(cases))),flush=True)
    memory={}
    case=max(cases,key=lambda c:c['pixels'])
    for name,fn in functions.items():
        tracemalloc.start();fn(dataset/case['image'],case['ocr'],case['task'],case['target'])
        memory[name]=tracemalloc.get_traced_memory()[1];tracemalloc.stop()
    proposal_rows=[]
    with OcrSession() as session:
        tavi_compact.propose(dataset/cases[0]['image'],cases[0]['task'],cases[0]['target'],ocr_fn=session)
        for index in manifest['proposal_case_indexes']:
            case=cases[index];results={}
            for name in (('baseline','optimized') if index%8==0 else ('optimized','baseline')):
                with patch.object(tavi_compact,'candidates',functions[name]),patch.object(tavi_compact,'prepare',preparers[name]):
                    start=time.perf_counter()
                    result=tavi_compact.propose(dataset/case['image'],case['task'],case['target'],ocr_fn=session,auto_click=True)
                    ms=(time.perf_counter()-start)*1000
                assert not result['auto_click']['candidate_eligible'] and result['hosted_calls']==0
                results[name]=result
                proposal_rows.append(dict(case=index,method=name,ms=ms))
            a,b=results['baseline'],results['optimized']
            assert a['review_packet']['proposed']==b['review_packet']['proposed']
            assert a['confidence']==b['confidence'] and a['review_reasons']==b['review_reasons']
            assert a['proposal_id']!=b['proposal_id']
        worker=session.process
    assert worker.poll() is not None
    feature={name:dict(n=len(values),median_ms=statistics.median(values)) for name,values in timings.items()}
    proposal={name:dict(n=sum(r['method']==name for r in proposal_rows),median_ms=statistics.median(r['ms'] for r in proposal_rows if r['method']==name)) for name in functions}
    summary=dict(feature_cases=len(cases),features_exact=True,proposals_exact=True,feature=feature,
        feature_speedup=feature['baseline']['median_ms']/feature['optimized']['median_ms'],
        proposal=proposal,proposal_speedup=proposal['baseline']['median_ms']/proposal['optimized']['median_ms'],
        optimizations=['Sampled floating-point pixels with legacy reduction rounding','Fast lossless PNG for local-only proposals; compact image-fallback encoding preserved'],
        tracked_peak_bytes=memory,memory_scope='tracemalloc Python/NumPy tracked peak; native Pillow bitmap allocations excluded.',
        automatic_candidates=0,hosted_calls=0,ocr_worker_closed=True,limits=manifest['limits'])
    (output/'feature-timings.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    (output/'proposal-timings.json').write_text(json.dumps(proposal_rows,indent=2),encoding='utf-8')
    (output/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('dataset',type=Path);p.add_argument('baseline',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();run(a.dataset,a.baseline,a.output)
