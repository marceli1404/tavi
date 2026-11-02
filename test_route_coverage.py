import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import tavi
from tavi_model import DecisionModel
from tavi_router import route_custom
from tavi_route_coverage import prepare,resolve,attach,read_input

BASE=Path(__file__).parent
MODELS=[dict(id=m,efforts=['low','medium','high'],default_effort='medium')
        for m in ('gpt-6-luna','gpt-6.1-sol','gpt-6-astra')]
TASK='Build the settings screen frontend'
SKILLS=[dict(id='new-ui',name='new-reviewed-interface',description='Build frontend settings screens.',path='fixture/new-ui/SKILL.md')]


def answer_for(plan,mapping):
    reviews=[]
    for p in plan['packets']:
        allowed={s['id'] for s in p['snapshot']['skills']}
        reviews.append(dict(packet_id=p['packet_id'],coverage=[dict(requirement_id=r['id'],
            skill_ids=[s for s in mapping.get(r['id'],[]) if s in allowed]) for r in p['snapshot']['requirements']]))
    return dict(context_id=plan['context_id'],reviews=reviews)


class RouteCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.model=DecisionModel.load(BASE/'models/tavi-v4-clean')

    def decision(self,skills=None,**kwargs):
        return route_custom(TASK,SKILLS if skills is None else skills,MODELS,self.model,**kwargs)

    def test_pending_review_withholds_launch_without_mutating_base(self):
        base=self.decision();original=copy.deepcopy(base)
        with patch('subprocess.run',side_effect=AssertionError('No backend')),patch('urllib.request.urlopen',side_effect=AssertionError('No network')):
            routed=attach(base,TASK,[TASK],SKILLS)
        self.assertEqual(base,original)
        self.assertEqual(routed['status'],'needs_review')
        self.assertEqual(routed['discovery']['status'],'needs_capability_review')
        self.assertIsNone(tavi.launch_plan(routed,TASK,'.'))
        self.assertIsNone(routed['capability_review']['probability'])
        self.assertFalse(routed['capability_review']['installation_authorized'])

    def test_review_can_select_unlearned_name_and_replace_search_advice(self):
        base=self.decision();self.assertEqual(base['discovery']['status'],'search_recommended')
        plan=prepare(TASK,[TASK],SKILLS);answer=answer_for(plan,{'r0':['new-ui']})
        reviewed=attach(base,TASK,[TASK],SKILLS,answer)
        self.assertEqual(reviewed['status'],base['status'])
        self.assertEqual(reviewed['model'],base['model']);self.assertEqual(reviewed['prediction'],base['prediction'])
        self.assertEqual(reviewed['skills'][0]['id'],'new-ui')
        self.assertEqual(reviewed['skills'][0]['selection'],'coverage-review')
        self.assertIsNone(reviewed['skills'][0]['score'])
        self.assertEqual(reviewed['discovery']['status'],'not_needed')
        self.assertNotIn('search_url',reviewed['discovery'])
        self.assertFalse(reviewed['capability_review']['reviewer_identity_verified'])
        self.assertFalse(reviewed['capability_review']['execution_capability_verified'])

    def test_large_inventory_is_complete_and_support_unions_across_packets(self):
        skills=[dict(id=f's{i:03}',name=f'skill-{i}',description=f'Capability {i}.') for i in range(205)]
        plan=prepare('Do both jobs',['First job','Last job'],skills)
        self.assertEqual(plan['packet_count'],3)
        ids=[s['id'] for p in plan['packets'] for s in p['snapshot']['skills']]
        self.assertEqual(set(ids),{s['id'] for s in skills});self.assertEqual(len(ids),205)
        answer=answer_for(plan,{'r0':['s000'],'r1':['s204']})
        answer['reviews'].reverse()
        reviewed=resolve('Do both jobs',['First job','Last job'],list(reversed(skills)),answer)
        self.assertFalse(reviewed['discovery_suggested'])
        self.assertEqual(reviewed['supporting_skill_ids'],['s000','s204'])

    def test_utf8_byte_limits_split_without_truncation(self):
        skills=[dict(id=f'u{i}',name=f'unicode-{i}',description='界'*3500) for i in range(31)]
        plan=prepare('Review the work',['Check it'],skills)
        self.assertGreater(plan['packet_count'],1)
        for p in plan['packets']:
            self.assertLessEqual(len(json.dumps(p['snapshot'],ensure_ascii=False).encode('utf-8')),131072)
            self.assertTrue(all(s['description']=='界'*3500 for s in p['snapshot']['skills']))
        self.assertEqual(sum(len(p['snapshot']['skills']) for p in plan['packets']),31)

    def test_task_requirement_description_inventory_and_exclusion_drift_refused(self):
        plan=prepare(TASK,[TASK],SKILLS);answer=answer_for(plan,{'r0':['new-ui']})
        changed=copy.deepcopy(SKILLS);changed[0]['description']='Audio only.'
        cases=[('different task',[TASK],SKILLS,()),(TASK,['different operation'],SKILLS,()),
               (TASK,[TASK],changed,()),(TASK,[TASK],[],()),
               (TASK,[TASK],SKILLS+[dict(id='other',name='other',description='Other')],()),
               (TASK,[TASK],SKILLS,('new-ui',))]
        for task,requirements,skills,excluded in cases:
            with self.subTest(task=task,excluded=excluded):
                with self.assertRaisesRegex(ValueError,'stale'):resolve(task,requirements,skills,answer,excluded)

    def test_every_packet_and_operation_required_exactly_once(self):
        skills=[dict(id=str(i),name=str(i),description='A capability.') for i in range(101)]
        plan=prepare('Task',['A','B'],skills)
        good=answer_for(plan,{'r0':['0'],'r1':['100']})
        for mode in ('missing_packet','duplicate_packet','missing_operation','unknown_skill'):
            answer=copy.deepcopy(good)
            if mode=='missing_packet':answer['reviews'].pop()
            if mode=='duplicate_packet':answer['reviews'].append(copy.deepcopy(answer['reviews'][0]))
            if mode=='missing_operation':answer['reviews'][0]['coverage'].pop()
            if mode=='unknown_skill':answer['reviews'][0]['coverage'][0]['skill_ids']=['invented']
            with self.subTest(mode=mode):
                with self.assertRaises(ValueError):resolve('Task',['A','B'],skills,answer)

    def test_excluded_skill_cannot_support_a_review(self):
        skills=SKILLS+[dict(id='other',name='other',description='Different operation.',path='other')]
        plan=prepare(TASK,[TASK],skills,['new-reviewed-interface'])
        self.assertEqual(plan['excluded_skill_ids'],['new-ui'])
        answer=answer_for(plan,{});answer['reviews'][0]['coverage'][0]['skill_ids']=['new-ui']
        with self.assertRaisesRegex(ValueError,'unknown'):resolve(TASK,[TASK],skills,answer,['new-ui'])

    def test_partial_review_is_advisory_and_keeps_discovery_without_authority(self):
        plan=prepare(TASK,['Build the UI','Export the project'],SKILLS)
        answer=answer_for(plan,{'r0':['new-ui']})
        routed=attach(self.decision(),TASK,['Build the UI','Export the project'],SKILLS,answer)
        self.assertEqual(routed['status'],'needs_review')
        self.assertEqual(routed['discovery']['status'],'search_recommended')
        self.assertEqual(routed['capability_review']['missing_requirement_ids'],['r1'])
        self.assertFalse(routed['discovery']['installation_authorized'])
        self.assertFalse(routed['capability_review']['review_grants_execution_authority'])
        self.assertIsNone(tavi.launch_plan(routed,TASK,'.'))

    def test_explicit_and_required_skills_remain_and_cannot_duplicate(self):
        skills=SKILLS+[dict(id='required',name='required-workflow',description='Required policy.',path='required')]
        base=self.decision(skills,requested_skills=['new-ui'],policy={'always_skills':['required-workflow']})
        plan=prepare(TASK,[TASK],skills);answer=answer_for(plan,{'r0':['new-ui']})
        routed=attach(base,TASK,[TASK],skills,answer)
        self.assertEqual({s['selection'] for s in routed['skills']},{'explicit','required-policy'})
        self.assertEqual(len(routed['skills']),2)

    def test_semantic_review_cannot_upgrade_a_withheld_model_route(self):
        base=self.decision();base['status']='needs_review';base['model']=None
        plan=prepare(TASK,[TASK],SKILLS)
        routed=attach(base,TASK,[TASK],SKILLS,answer_for(plan,{'r0':['new-ui']}))
        self.assertEqual(routed['status'],'needs_review');self.assertIsNone(routed['model'])

    def test_empty_inventory_still_requires_complete_review(self):
        plan=prepare('Task',['Operation'],[])
        self.assertEqual(plan['packet_count'],1)
        reviewed=resolve('Task',['Operation'],[],answer_for(plan,{}))
        self.assertTrue(reviewed['discovery_suggested']);self.assertEqual(reviewed['eligible_skill_count'],0)

    def test_direct_host_work_does_not_falsely_require_a_download(self):
        plan=prepare('Summarize the supplied notes',['Summarize the notes'],[])
        answer=answer_for(plan,{});answer['native_requirement_ids']=['r0']
        reviewed=resolve('Summarize the supplied notes',['Summarize the notes'],[],answer)
        self.assertFalse(reviewed['discovery_suggested'])
        self.assertEqual(reviewed['native_requirement_ids'],['r0'])
        self.assertFalse(reviewed['native_capability_verified'])
        self.assertFalse(reviewed['review_grants_execution_authority'])

    def test_direct_and_skill_operations_can_mix_without_dropping_packets(self):
        plan=prepare(TASK,['Build UI','Summarize notes'],SKILLS)
        answer=answer_for(plan,{'r0':['new-ui']});answer['native_requirement_ids']=['r1']
        reviewed=resolve(TASK,['Build UI','Summarize notes'],SKILLS,answer)
        self.assertFalse(reviewed['discovery_suggested']);self.assertEqual(reviewed['supporting_skill_ids'],['new-ui'])
        for invalid in (['r2'],['r1','r1'],[None]):
            bad=copy.deepcopy(answer);bad['native_requirement_ids']=invalid
            with self.assertRaises(ValueError):resolve(TASK,['Build UI','Summarize notes'],SKILLS,bad)
        conflict=copy.deepcopy(answer);conflict['native_requirement_ids']=['r0']
        with self.assertRaises(ValueError):resolve(TASK,['Build UI','Summarize notes'],SKILLS,conflict)

    def test_pending_mode_withholds_unreviewed_learned_skill_choices(self):
        skills=[dict(id='ui',name='ui-design',description='Build frontend screens.',path='ui')]
        base=self.decision(skills);self.assertTrue(any(s['selection']=='learned' for s in base['skills']))
        pending=attach(base,TASK,[TASK],skills)
        self.assertFalse(pending['skills']);self.assertFalse(pending['explanation']['learned_skills'])
        self.assertTrue(base['skills'])

    def test_duplicate_ids_unknown_exclusions_and_bounds_fail(self):
        for skills,excluded in [(SKILLS*2,()),(SKILLS,('unknown',)),(SKILLS*1001,())]:
            with self.assertRaises(ValueError):prepare(TASK,[TASK],skills,excluded)
        with self.assertRaises(ValueError):prepare(TASK,[],SKILLS)
        with self.assertRaises(ValueError):prepare(TASK,['same','same'],SKILLS)

    def test_total_packet_collection_and_context_byte_limits_fail_closed(self):
        large=[dict(id=str(i),name=str(i),description='x'*4000) for i in range(600)]
        with self.assertRaisesRegex(ValueError,'2MiB'):prepare('Task',['Operation'],large)
        wide=[dict(id='界'*195+str(i),name='界'*200,description='A') for i in range(900)]
        with self.assertRaisesRegex(ValueError,'1MiB'):prepare('Task',['Operation'],wide)

    def test_reviewed_route_can_prepare_an_offline_claude_plan(self):
        from tavi_providers import claude_catalog,provider_roles
        base=route_custom(TASK,SKILLS,claude_catalog(),self.model,roles=provider_roles('claude',{}))
        plan=prepare(TASK,[TASK],SKILLS)
        reviewed=attach(base,TASK,[TASK],SKILLS,answer_for(plan,{'r0':['new-ui']}))
        with patch('tavi_providers.claude_command',return_value=['claude.exe']),\
             patch('subprocess.run',side_effect=AssertionError('No live Claude request')):
            launch=tavi.launch_plan(reviewed,TASK,'.','claude')
        self.assertFalse(launch['executed']);self.assertEqual(launch['argv'][launch['argv'].index('--permission-mode')+1],'plan')
        self.assertNotIn('--dangerously-skip-permissions',launch['argv'])

    def test_duplicate_json_and_oversized_input_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'answer.json';path.write_text('{"context_id":"a","context_id":"b","reviews":[]}')
            with self.assertRaisesRegex(ValueError,'Duplicate'):read_input(path)
            path.write_bytes(b' '*262145)
            with self.assertRaisesRegex(ValueError,'256KiB'):read_input(path)

    def test_cli_roundtrip_and_stale_answer_without_backend_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);config=root/'config.json';requirements=root/'requirements.json';answer_file=root/'answer.json'
            config.write_text(json.dumps(dict(skill_roots=[],model_path=str(BASE/'models/tavi-v4-clean'))))
            requirements.write_text(json.dumps([TASK]))
            argv=['tavi.py','--config',str(config),'route',TASK,'--coverage-requirements',str(requirements)]
            def run(extra=(),skills=SKILLS):
                stdout=io.StringIO();stderr=io.StringIO()
                with patch('sys.argv',argv+list(extra)),patch('tavi.scan_skills',return_value=skills),\
                     patch('tavi.model_catalog',return_value=MODELS),\
                     patch('subprocess.run',side_effect=AssertionError('No backend call')),\
                     patch('urllib.request.urlopen',side_effect=AssertionError('No network call')),\
                     contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):code=tavi.main()
                return code,stdout.getvalue(),stderr.getvalue()
            code,raw,error=run();self.assertEqual(code,0,error)
            pending=json.loads(raw);answer=answer_for(pending['capability_review'],{'r0':['new-ui']})
            answer_file.write_text(json.dumps(answer))
            code,raw,error=run(['--coverage-answer',str(answer_file)])
            self.assertEqual(code,0,error);self.assertEqual(json.loads(raw)['discovery']['status'],'not_needed')
            changed=copy.deepcopy(SKILLS);changed[0]['description']='Changed.'
            code,raw,error=run(['--coverage-answer',str(answer_file)],changed)
            self.assertEqual(code,1);self.assertIn('stale',error)
            code,raw,error=run(['--execute'])
            self.assertEqual(code,1);self.assertIn('Launch withheld',error)
            self.assertIsNone(json.loads(raw)['launch_plan'])

    def test_cli_requires_requirements_and_rejects_legacy_backend(self):
        for extra in (['--coverage-answer','missing.json'],
                      ['--backend','laya','--coverage-requirements','missing.json'],
                      ['--coverage-requirements','-','--coverage-answer','-']):
            stderr=io.StringIO()
            with patch('sys.argv',['tavi.py','--config','missing-config.json','route',TASK]+extra),\
                 patch('subprocess.run',side_effect=AssertionError('No backend')),contextlib.redirect_stderr(stderr):
                self.assertEqual(tavi.main(),1)
            self.assertNotIn('missing-config',stderr.getvalue())


if __name__=='__main__':unittest.main()
