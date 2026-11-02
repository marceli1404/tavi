import copy
import io
import json
import unittest
from datetime import datetime, timezone, timedelta
from tavi_control_compact import compact_batch
from tavi_control_stream import run
from tavi_controls import resolve_many


class CompactControlTests(unittest.TestCase):
    def batch(self, age=0, unavailable=False, duplicate=False):
        control=dict(id='go',label='Go',role='button',visible=True,enabled=not unavailable,
                     bounds=[10,10,80,30],context='Search')
        snapshot=dict(format='tavi-control-snapshot-v1',snapshot_id='frame',
                      captured_at=(datetime.now(timezone.utc)-timedelta(seconds=age)).isoformat(),
                      source='supported_browser_dom',viewport=[800,600],controls=[control])
        if duplicate: snapshot['controls'].append(dict(control,id='other'))
        queries=[dict(id='present',task='Search',target='Go'),dict(id='missing',task='Close',target='Close')]
        return snapshot, queries, resolve_many(snapshot,queries)

    def expand(self, compact):
        restored=copy.deepcopy(compact)
        shared=restored.pop('shared_proposal_fields')
        restored['proposals']=[dict(shared,**p) for p in restored['proposals']]
        restored['format']='tavi-control-batch-v1'
        return restored

    def test_lossless_status_and_authority(self):
        for options in ({},{'age':7},{'age':-10},{'unavailable':True},{'duplicate':True}):
            with self.subTest(options=options):
                _,_,batch=self.batch(**options)
                before=copy.deepcopy(batch); compact=compact_batch(batch)
                self.assertEqual(batch,before)
                self.assertEqual(self.expand(compact),batch)
                self.assertTrue(compact['requires_live_host_check'])
                self.assertFalse(compact['authorization_granted'])
                self.assertFalse(compact['executed_actions'])

    def test_detached_and_per_query_identity(self):
        _,_,batch=self.batch(); compact=compact_batch(batch)
        self.assertNotEqual(compact['proposals'][0]['task_sha256'],compact['proposals'][1]['task_sha256'])
        compact['proposals'][0]['candidate']['bounds'][0]=100
        self.assertEqual(batch['proposals'][0]['candidate']['bounds'][0],10)

    def test_refuse_authority_escalation(self):
        _,_,batch=self.batch()
        for key,value in [('authorization_granted',True),('requires_live_host_check',False),('executed_actions',True)]:
            for target in ('batch','proposal'):
                changed=copy.deepcopy(batch)
                (changed if target=='batch' else changed['proposals'][0])[key]=value
                with self.assertRaises(ValueError): compact_batch(changed)

    def test_stream_opt_in_and_invalid_type_recovery(self):
        snapshot,queries,_=self.batch()
        requests=[dict(snapshot=snapshot,queries=queries),dict(snapshot=snapshot,queries=queries,compact=True),
                  dict(snapshot=snapshot,queries=queries,compact=1),dict(snapshot=snapshot,queries=queries,compact=False)]
        output=io.StringIO();self.assertEqual(run(io.StringIO(''.join(json.dumps(x)+'\n' for x in requests)),output),0)
        events=[json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual([e.get('format') for e in events[1:]],
                         ['tavi-control-batch-v1','tavi-control-batch-compact-v1',None,'tavi-control-batch-v1'])
        self.assertEqual(events[3]['status'],'error')
        a,b=events[1],self.expand(events[2])
        for result in (a,b):
            for p in result['proposals']: p.pop('age_seconds')
        self.assertEqual(a,b)


if __name__=='__main__': unittest.main()
