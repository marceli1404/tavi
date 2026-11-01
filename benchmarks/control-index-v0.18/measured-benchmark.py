"""Bounded offline resolver parity and preparation-only timing; no UI actions."""
import copy,hashlib,importlib.util,json,random,statistics,sys,time
from datetime import datetime,timedelta,timezone
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE))
from tavi_controls import ControlIndex,resolve,resolve_many
NOW=datetime(2026,11,1,tzinfo=timezone.utc)

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def inventory(n):
    return dict(format='tavi-control-snapshot-v1',snapshot_id='benchmark-'+str(n),source='supported_browser_dom',
        captured_at=NOW.isoformat(),viewport=[1280,720],controls=[dict(id=str(i),label='Control '+str(i),
        role='button' if i%2 else 'link',visible=True,enabled=i%11!=0,bounds=[10,20,100,30],context='Group '+str(i%7)) for i in range(n)])

def run(root):
    root=Path(root);legacy_path=root/'legacy-tavi-controls.py'
    spec=importlib.util.spec_from_file_location('legacy_controls',legacy_path);legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)
    rng=random.Random(20261101);cases=[]
    for index in range(200):
        snapshot=inventory(rng.randrange(0,26));snapshot['captured_at']=(NOW-timedelta(seconds=rng.choice([-2,0,2,6]))).isoformat()
        for c in snapshot['controls']:
            c.update(label=rng.choice(['Go','  gO ','Go back','Gó']),context=rng.choice(['Navigation','Search','Cafe\u0301']),
                     visible=rng.choice([True,False]),enabled=rng.choice([True,False]),role=rng.choice(['button','link','tab']),
                     bounds=[rng.choice([10,1300]),20,rng.choice([0,100]),30])
        kwargs=dict(task='Press Go',target=rng.choice(['Go','Gó','Missing']),role=rng.choice(['button','link','tab']),
                    context=rng.choice([None,'Navigation','Search','CAFÉ']),offline=rng.choice([True,False]))
        cases.append(dict(snapshot=snapshot,query=kwargs))
    (root/'parity-cases.json').write_text(json.dumps(cases,indent=2))
    protocol=dict(format='tavi-control-index-benchmark-v1',legacy_source_sha256=sha(legacy_path),source_sha256=sha(BASE/'tavi_controls.py'),
        benchmark_source_sha256=sha(__file__),cases_sha256=sha(root/'parity-cases.json'),seed=20261101,
        inventories=[10,1000],queries_per_batch=12,rounds=10,order='Alternating legacy/batch per round',
        clock='Frozen logical time; no live action',scope='In-memory preparation only; excludes capture, file parse/startup, agent, input and UI response.')
    (root/'protocol.json').write_text(json.dumps(protocol,indent=2))
    for case in cases:
        old=legacy.resolve(case['snapshot'],now=NOW,**case['query'])
        indexed=ControlIndex(case['snapshot']).resolve(now=NOW,**case['query'])
        if old!=indexed or old!=resolve(case['snapshot'],now=NOW,**case['query']):raise ValueError('Resolver parity failed')
    timings={}
    for n in protocol['inventories']:
        snapshot=inventory(n)
        queries=[dict(task='Inspect control '+str(i),target='Control '+str(i%n),role='button' if (i%n)%2 else 'link') for i in range(12)]
        functions={'legacy':lambda:[legacy.resolve(snapshot,now=NOW,**q) for q in queries],
                   'batch':lambda:resolve_many(snapshot,queries,now=NOW)['proposals']}
        for fn in functions.values():fn()
        values={name:[] for name in functions};single={'legacy':[],'current':[]};prepared=ControlIndex(snapshot);warm=[];build=[]
        for round_index in range(10):
            for name in (['legacy','batch'] if round_index%2==0 else ['batch','legacy']):
                start=time.perf_counter_ns();result=functions[name]();values[name].append((time.perf_counter_ns()-start)/1e6)
            start=time.perf_counter_ns();ControlIndex(snapshot);build.append((time.perf_counter_ns()-start)/1e6)
            for q in queries:
                start=time.perf_counter_ns();prepared.resolve(now=NOW,**q);warm.append((time.perf_counter_ns()-start)/1e6)
            for name,fn in [('legacy',legacy.resolve),('current',resolve)]:
                start=time.perf_counter_ns();fn(snapshot,now=NOW,**queries[0]);single[name].append((time.perf_counter_ns()-start)/1e6)
        if functions['legacy']()!=functions['batch']():raise ValueError('Batch output mismatch')
        medians={name:statistics.median(v) for name,v in values.items()}
        timings[str(n)]=dict(batch_median_ms=medians,batch_speed_ratio=medians['legacy']/medians['batch'],
            index_build_median_ms=statistics.median(build),prepared_query_median_ms=statistics.median(warm),
            one_shot_median_ms={name:statistics.median(v) for name,v in single.items()},raw_batch_ms=values)
    report=dict(protocol_sha256=sha(root/'protocol.json'),parity_cases=200,all_outputs_equal=True,timings=timings,
                authorization_granted=False,executed_actions=False,scope=protocol['scope'])
    (root/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)

if __name__=='__main__':run(sys.argv[1])
