import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from tavi_controls import resolve, resolve_file

NOW = datetime(2026, 10, 29, 8, tzinfo=timezone.utc)


def fixture():
    return dict(format='tavi-control-snapshot-v1', snapshot_id='frame1',
                source='supported_browser_dom', captured_at=NOW.isoformat(), viewport=[800, 600],
                controls=[dict(id='go', label='Go', role='button', visible=True, enabled=True,
                               bounds=[10, 20, 80, 30], context='Navigation')])


class ControlTests(unittest.TestCase):
    def run_case(self, s=None, **kw):
        return resolve(s or fixture(), 'Press Go', 'Go', now=NOW, **kw)

    def test_exact_match_is_not_permission_or_probability(self):
        r=self.run_case()
        self.assertEqual(r['status'],'host_verification_required')
        self.assertIsNone(r['probability'])
        self.assertFalse(r['authorization_granted']);self.assertFalse(r['executed_actions'])
        self.assertTrue(r['requires_live_host_check'])

    def test_exact_not_fuzzy(self):
        s=fixture();s['controls'][0]['label']='Go back'
        self.assertEqual(self.run_case(s)['reason'],'no_exact_control')

    def test_case_whitespace(self):
        s=fixture();s['controls'][0]['label']='  gO\n '
        self.assertIsNotNone(self.run_case(s)['candidate'])

    def test_ambiguity_and_context(self):
        s=fixture();c=copy.deepcopy(s['controls'][0]);c.update(id='go2',context='Search');s['controls'].append(c)
        self.assertEqual(self.run_case(s)['reason'],'ambiguous_control')
        self.assertEqual(self.run_case(s,context='Search')['candidate']['id'],'go2')

    def test_wrong_role(self):
        s=fixture();s['controls'][0]['role']='link'
        self.assertEqual(self.run_case(s)['reason'],'no_exact_control')

    def test_unavailable(self):
        for field,value in [('visible',False),('enabled',False),('bounds',[900,0,10,10]),('bounds',[0,0,0,30])]:
            with self.subTest(field=field,value=value):
                s=fixture();s['controls'][0][field]=value
                self.assertEqual(self.run_case(s)['reason'],'control_unavailable')

    def test_stale_future_and_offline(self):
        s=fixture();s['captured_at']=(NOW-timedelta(seconds=6)).isoformat()
        self.assertEqual(self.run_case(s)['reason'],'stale_snapshot')
        self.assertEqual(self.run_case(s,offline=True)['status'],'offline_match')
        s['captured_at']=(NOW+timedelta(seconds=1)).isoformat()
        self.assertEqual(self.run_case(s,offline=True)['reason'],'future_snapshot')

    def test_hash_binds_inventory_and_task(self):
        a=self.run_case();s=fixture();s['controls'][0]['bounds'][0]=11;b=self.run_case(s)
        self.assertNotEqual(a['snapshot_sha256'],b['snapshot_sha256'])
        c=resolve(fixture(),'Click Go after review','Go',now=NOW)
        self.assertNotEqual(a['task_sha256'],c['task_sha256'])

    def test_duplicate_id_rejected(self):
        s=fixture();s['controls'].append(copy.deepcopy(s['controls'][0]))
        with self.assertRaises(ValueError):self.run_case(s)

    def test_malformed_states_and_geometry(self):
        for field,value in [('enabled','true'),('visible',1),('bounds',[True,0,20,20]),('bounds',[0,0,float('nan'),20]),('bounds',[0,0,-1,20]),('context',None)]:
            with self.subTest(field=field,value=value):
                s=fixture();s['controls'][0][field]=value
                with self.assertRaises(ValueError):self.run_case(s)

    def test_missing_timezone_or_invalid_envelope(self):
        for key,value in [('captured_at','2026-10-29T08:00:00'),('source','my_own_driver'),('viewport',[0,600]),('controls',None),('snapshot_id','')]:
            s=fixture();s[key]=value
            with self.assertRaises(ValueError):self.run_case(s)

    def test_no_controls_review(self):
        s=fixture();s['controls']=[]
        self.assertEqual(self.run_case(s)['reason'],'no_exact_control')

    def test_bounded_file(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'s.json';p.write_text(json.dumps(fixture()),encoding='utf-8')
            self.assertEqual(resolve_file(p,'Press Go','Go',now=NOW)['candidate']['id'],'go')
            p.write_bytes(b' '*2000001)
            with self.assertRaises(ValueError):resolve_file(p,'Press Go','Go')


if __name__=='__main__':unittest.main()
