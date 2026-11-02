"""Paired cache-only benchmark; no capture, hosted inference or input actions."""
import hashlib,importlib.util,json,statistics,sys,tempfile,time,os
from pathlib import Path
from unittest.mock import patch
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE))
import tavi_vision as current

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def clean(r):return {k:v for k,v in r.items() if k not in ('elapsed_ms','cache_hit','hosted_request_this_call')}
def run():
 oldpath=BASE/'output/vision-cache-profile-20261101/tavi_vision-before.py'
 assert sha(oldpath)=='4d1d7ac11b0792892a9b0abd24862806abe8b659caac6f4507392efe50feb8d2'
 spec=importlib.util.spec_from_file_location('cache_baseline',oldpath);old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
 out=BASE/'output/vision-cache-speed-20261101-run2';out.mkdir(exist_ok=False)
 cases=[BASE/'output/vision-speed-20261028'/name for name in ('clear-text.png','duplicate-text.png','icon-only.png')]
 manifest=dict(old_sha256=sha(oldpath),new_sha256=sha(BASE/'tavi_vision.py'),cases=[dict(file=p.name,sha256=sha(p)) for p in cases],rounds_per_case=20,order='alternate old/new per case and round',scope='Exact-input saved-image observation cache only; excludes capture, live-state verification, agent reasoning, clicks, hosted inference and interpreter startup. Same native Windows OCR callback initializes both separate caches (baseline source relocated away from bundled script); measured hits must not OCR or prepare. No concurrent training.')
 (out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
 records=[];cold=[]
 with tempfile.TemporaryDirectory(prefix='tavi-paired-cache-') as temp:
  for ci,image in enumerate(cases):
   cache={name:Path(temp)/f'{ci}-{name}' for name in ('old','new')};modules={'old':old,'new':current}
   initial={name:m.analyze(image,'Read this screen',mode='local',cache=cache[name],ocr_fn=current.local_ocr) for name,m in modules.items()}
   assert clean(initial['old'])==clean(initial['new']), 'Cold native OCR output mismatch'
   for name in modules:
    for entry in cache[name].glob('*.json'):os.utime(entry,(time.time()-1,time.time()-1))
   for round in range(20):
    sample={};values={}
    for name in (('old','new') if (ci+round)%2==0 else ('new','old')):
     m=modules[name];start=time.perf_counter()
     with patch.object(m,'local_ocr',side_effect=AssertionError('Warm cache called OCR')),patch.object(m,'hosted',side_effect=AssertionError('Benchmark must not host')):
      values[name]=m.analyze(image,'Read this screen',mode='local',cache=cache[name])
     sample[name]=(time.perf_counter()-start)*1000
     assert values[name]['cache_hit'] and not values[name]['hosted_request_this_call'] and not values[name]['executed_actions']
    assert clean(values['old'])==clean(values['new'])
    records.append(dict(case=image.name,round=round,old_ms=sample['old'],new_ms=sample['new']))
   # Paired cold-path timing with identical no-I/O OCR stub, cache disabled.
   for round in range(5):
    sample={};values={}
    for name in (('old','new') if round%2==0 else ('new','old')):
     start=time.perf_counter();values[name]=modules[name].analyze(image,'Read this screen',mode='local',cache=None,ocr_fn=lambda p:dict(status='available',text='fixture',words=[]));sample[name]=(time.perf_counter()-start)*1000
    assert clean(values['old'])==clean(values['new'])
    cold.append(dict(case=image.name,round=round,old_ms=sample['old'],new_ms=sample['new']))
 warm_old=statistics.median(r['old_ms'] for r in records);warm_new=statistics.median(r['new_ms'] for r in records)
 summary=dict(warm_pairs=len(records),all_outputs_equal=True,warm_old_median_ms=warm_old,warm_new_median_ms=warm_new,warm_ratio=warm_old/warm_new,cold_pairs=len(cold),cold_old_median_ms=statistics.median(r['old_ms'] for r in cold),cold_new_median_ms=statistics.median(r['new_ms'] for r in cold),scope=manifest['scope'])
 (out/'report.json').write_text(json.dumps(dict(summary=summary,warm_samples=records,cold_samples=cold),indent=2),encoding='utf-8')
 print(json.dumps(summary))
if __name__=='__main__':run()
