"""Measure lossless wire bytes and response encoding, not full agent speed."""
import copy
import hashlib
import json
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from tavi_controls import resolve_many
from tavi_control_compact import compact_batch


def snapshot():
    controls=[dict(id='go',label='Go',role='button',visible=True,enabled=True,bounds=[10,10,80,30]),
              dict(id='archive1',label='Archive',role='button',visible=True,enabled=True,bounds=[110,10,80,30]),
              dict(id='archive2',label='Archive',role='button',visible=True,enabled=True,bounds=[210,10,80,30]),
              dict(id='delete',label='Delete',role='button',visible=True,enabled=False,bounds=[310,10,80,30])]
    return dict(format='tavi-control-snapshot-v1',snapshot_id='synthetic-frame',
                source='supported_browser_dom',captured_at=datetime.now(timezone.utc).isoformat(),
                viewport=[800,600],controls=controls)


def expand(value):
    restored=copy.deepcopy(value);shared=restored.pop('shared_proposal_fields')
    restored['proposals']=[dict(shared,**p) for p in restored['proposals']]
    restored['format']='tavi-control-batch-v1'
    return restored


def main():
    out=Path('output/control-compact-20261102');out.mkdir(parents=True,exist_ok=False)
    results=[]
    for count in (1,10,100):
        queries=[dict(id=str(i),task='Inspect result '+str(i),target=['Go','Close','Archive','Delete'][i%4]) for i in range(count)]
        batch=resolve_many(snapshot(),queries)
        packet=compact_batch(batch)
        assert expand(packet)==batch
        sizes={name:len(json.dumps(value,ensure_ascii=False,allow_nan=False).encode())
               for name,value in [('full',batch),('compact',packet)]}
        times={'full':[],'compact':[]}
        for pair in range(50):
            for mode in (['full','compact'] if pair%2==0 else ['compact','full']):
                start=time.perf_counter_ns()
                encoded=json.dumps(batch if mode=='full' else compact_batch(batch),ensure_ascii=False,allow_nan=False)
                times[mode].append((time.perf_counter_ns()-start)/1000)
        results.append(dict(queries=count,bytes=sizes,reduction_percent=100*(1-sizes['compact']/sizes['full']),
                            encoding_median_us={k:statistics.median(v) for k,v in times.items()},
                            paired_encoding_us=times,lossless=True))
    process=subprocess.Popen([sys.executable,'tavi.py','--config',str(out/'missing.json'),'target-controls-stream'],
                             stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8')
    try:
        assert json.loads(process.stdout.readline())['status']=='ready'
        current=snapshot();queries=[dict(task='Inspect '+label,target=label) for label in ('Go','Close','Archive','Delete')]
        replies=[]
        for compact in (False,True):
            process.stdin.write(json.dumps(dict(snapshot=current,queries=queries,compact=compact))+'\n');process.stdin.flush()
            value=json.loads(process.stdout.readline());value=expand(value) if compact else value
            for p in value['proposals']:p.pop('age_seconds')
            replies.append(value)
        assert replies[0]==replies[1]
        assert [p['reason'] for p in replies[0]['proposals']]==['unique_exact_control','no_exact_control','ambiguous_control','control_unavailable']
        process.stdin.close();assert process.wait(timeout=10)==0
    finally:
        if process.poll() is None:process.terminate();process.wait(timeout=10)
    report=dict(cases=results,cli_roundtrip_parity=True,limits='Synthetic supplied host records. Bytes and local response encoding only; excludes acquisition, resolution, transport, agent reasoning, hosted inference, clicks and app response. CPU training was active; timings are contextual. No full computer-use speedup or token-count claim.',
                source_hashes={(Path(p).name if p == __file__ else p):hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in
                               ('tavi.py','tavi_controls.py','tavi_control_stream.py','tavi_control_compact.py',__file__)})
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({**report,'cases':[{k:v for k,v in c.items() if k!='paired_encoding_us'} for c in results]}))


if __name__=='__main__':main()
