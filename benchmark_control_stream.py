"""Synthetic CLI round-trip benchmark; excludes host acquisition and actions."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess,sys,time,statistics

def clean(result):
 result=dict(result);result.pop('request_id',None);result.pop('observation_reused',None)
 for p in result['proposals']:p.pop('age_seconds',None)
 return result

def main():
 out=Path('output/control-stream-speed-20261101');out.mkdir(exist_ok=False);query=[dict(task='Open the result',target='Go')];(out/'queries.json').write_text(json.dumps(query))
 started=time.perf_counter();process=subprocess.Popen([sys.executable,'tavi.py','--config',str(out/'missing-config.json'),'target-controls-stream'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',bufsize=1)
 trials=[]
 try:
  ready=json.loads(process.stdout.readline());assert ready['status']=='ready' and ready['authorization_granted'] is False;startup=(time.perf_counter()-started)*1000
  for i in range(12):
   snapshot=dict(format='tavi-control-snapshot-v1',snapshot_id='synthetic-'+str(i),captured_at=datetime.now(timezone.utc).isoformat(),source='supported_browser_dom',viewport=[800,600],controls=[dict(id='go',label='Go' if i%3!=1 else 'Stop',role='button',visible=True,enabled=True,bounds=[10,10,80,30])])
   if i%3==2:snapshot['controls'].append(dict(snapshot['controls'][0],id='other'))
   path=out/'snapshot.json';path.write_text(json.dumps(snapshot));times={};results={}
   for mode in (['oneshot','stream'] if i%2==0 else ['stream','oneshot']):
    start=time.perf_counter()
    if mode=='stream':
     process.stdin.write(json.dumps(dict(id=str(i),snapshot=snapshot,queries=query))+'\n');process.stdin.flush();result=json.loads(process.stdout.readline())
    else:
     r=subprocess.run([sys.executable,'tavi.py','--config',str(out/'missing-config.json'),'target-controls-batch',str(path),str(out/'queries.json')],capture_output=True,text=True,encoding='utf-8',check=True,timeout=20);result=json.loads(r.stdout)
    times[mode]=(time.perf_counter()-start)*1000;results[mode]=clean(result)
   assert results['oneshot']==results['stream'];assert results['stream']['authorization_granted'] is False
   trials.append(dict(pair=i,kind=['unique','missing','ambiguous'][i%3],times_ms=times,result=results['stream']))
  process.stdin.close();assert process.wait(timeout=10)==0
 finally:
  if process.poll() is None:process.terminate();process.wait(timeout=10)
 med={m:statistics.median(t['times_ms'][m] for t in trials) for m in ['oneshot','stream']}
 report=dict(pairs=len(trials),alternating_order=True,fixtures='Synthetic supplied DOM-like records; unique, missing, ambiguous. No real UI.',median_ms=med,ratio=med['oneshot']/med['stream'],stream_startup_ms=startup,all_outputs_match_except_age=True,missing_config_cli_passed=True,limits='CLI roundtrip only; stream warm requests exclude startup, reported separately. Includes one-shot startup/file read versus stream pipe parse. Excludes acquisition, live host verification, agent reasoning, clicks and app response. Not full computer-use speed.',source_hashes={n:hashlib.sha256(Path(n).read_bytes()).hexdigest() for n in ['tavi.py','tavi_controls.py','tavi_control_stream.py',__file__]},trials=trials)
 (out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k!='trials'}))
if __name__=='__main__':main()
