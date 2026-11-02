import io,json,unittest
from datetime import datetime,timezone,timedelta
from tavi_control_stream import run
class ControlStreamTests(unittest.TestCase):
 def snapshot(self,age=0,ident='frame'):
  return dict(format='tavi-control-snapshot-v1',snapshot_id=ident,captured_at=(datetime.now(timezone.utc)-timedelta(seconds=age)).isoformat(),source='supported_browser_dom',viewport=[800,600],controls=[dict(id='go',label='Go',role='button',visible=True,enabled=True,bounds=[10,10,80,30])])
 def request(self,s=None):return dict(snapshot=self.snapshot() if s is None else s,queries=[dict(task='Open the result',target='Go')])
 def send(self,requests):
  out=io.StringIO();code=run(io.StringIO(''.join(json.dumps(r)+'\n' for r in requests)),out);return code,[json.loads(x) for x in out.getvalue().splitlines()]
 def test_fresh_request_parity_and_authority(self):
  from tavi_controls import resolve_many
  r=self.request();code,events=self.send([r]);self.assertEqual(code,0);got=events[1];expected=resolve_many(r['snapshot'],r['queries']);got.pop('request_id');self.assertFalse(got.pop('observation_reused'));got['proposals'][0].pop('age_seconds');expected['proposals'][0].pop('age_seconds');self.assertEqual(got,expected);self.assertIsNone(got['proposals'][0]['probability']);self.assertFalse(got['authorization_granted'])
 def test_stale_future_ambiguous_unavailable(self):
  stale=self.request(self.snapshot(6));future=self.request(self.snapshot(-10));ambiguous=self.request();second=dict(ambiguous['snapshot']['controls'][0]);second['id']='other';ambiguous['snapshot']['controls'].append(second);disabled=self.request();disabled['snapshot']['controls'][0]['enabled']=False
  _,events=self.send([stale,future,ambiguous,disabled]);self.assertEqual([x['proposals'][0]['reason'] for x in events[1:]],['stale_snapshot','future_snapshot','ambiguous_control','control_unavailable'])
 def test_new_snapshot_required_and_no_state_reuse(self):
  a=self.request();b=self.request(self.snapshot(0,'frame2'));b['snapshot']['controls'][0]['label']='Stop';_,events=self.send([a,dict(queries=a['queries']),b]);self.assertEqual(events[2]['status'],'error');self.assertEqual(events[3]['proposals'][0]['reason'],'no_exact_control')
 def test_forbidden_options_and_recovery(self):
  a=self.request();a['offline']=True;_,events=self.send([a,self.request()]);self.assertEqual(events[1]['status'],'error');self.assertEqual(events[2]['proposals'][0]['reason'],'unique_exact_control')
 def test_duplicate_fields_and_size_terminate(self):
  out=io.StringIO();run(io.StringIO('{"id":"x","id":"y"}\n'),out);self.assertEqual(json.loads(out.getvalue().splitlines()[1])['status'],'error')
  out=io.StringIO();self.assertEqual(run(io.StringIO('x'*2000001+'\n'),out),1);self.assertEqual(len(out.getvalue().splitlines()),2)
if __name__=='__main__':unittest.main()
