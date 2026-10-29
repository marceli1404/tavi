import copy
import json
import os
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from tavi import launch_plan
from tavi_model import DecisionModel
from tavi_providers import claude_catalog,claude_command,claude_plan,claude_status,provider_roles
from tavi_router import route_custom

BASE=Path(__file__).parent

class ProviderTests(unittest.TestCase):
    def test_offline_claude_inventory_is_utf8_on_legacy_windows_pipes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);skill=root/'unicode';skill.mkdir()
            (skill/'SKILL.md').write_text('---\nname: unicode-test\ndescription: Read task → plan and Ελληνικά.\n---\n',encoding='utf-8')
            config=root/'config.json';config.write_text(json.dumps({'skill_roots':[str(root)]}),encoding='utf-8')
            env=dict(os.environ,PYTHONIOENCODING='cp1252')
            proc=subprocess.run([sys.executable,str(BASE/'tavi.py'),'--config',str(config),'inventory','--provider','claude'],
                                capture_output=True,env=env,timeout=30)
            self.assertEqual(proc.returncode,0,proc.stderr.decode('utf-8'))
            data=json.loads(proc.stdout.decode('utf-8'))
            self.assertIn('→',json.dumps(data,ensure_ascii=False))
    @classmethod
    def setUpClass(cls):cls.model=DecisionModel.load(BASE/'models/tavi-v4-clean')

    def decision(self,prompt='Fix a mobile navigation menu',**kwargs):
        return route_custom(prompt,[],claude_catalog(),self.model,roles=provider_roles('claude',{}),**kwargs)

    def test_workload_maps_to_claude_aliases(self):
        decision=self.decision()
        self.assertEqual(decision['model']['id'],'sonnet')
        self.assertEqual(self.decision(preference='speed')['model']['id'],'haiku')
        self.assertEqual(self.decision(preference='quality')['model']['id'],'opus')

    def test_codex_roles_do_not_leak_into_claude_policy(self):
        self.assertEqual(provider_roles('claude',{'model_roles':{'balanced':['codex-only']}})['balanced'],['sonnet'])

    def test_unknown_model_and_exclusions_are_respected(self):
        with self.assertRaises(ValueError):self.decision(requested_model='gpt-6.1-sol')
        self.assertIsNone(self.decision(excluded_models=['sonnet'])['model'])

    def test_plan_restricts_model_tools_and_never_bypasses_permissions(self):
        with patch('tavi_providers.claude_command',return_value=['claude.exe']):plan=claude_plan(self.decision(),'Task','.')
        argv=plan['argv'];self.assertIn('--print',argv);self.assertIn('Read,Glob,Grep',argv);self.assertIn('mcp__*',argv)
        self.assertIn('--permission-prompts',argv);self.assertNotIn('--dangerously-skip-permissions',argv)
        self.assertEqual(argv[argv.index('--permission-mode')+1],'plan');self.assertFalse(plan['executed'])

    def test_interactive_handoff_uses_native_approvals_and_literal_task(self):
        task='Fix "quotes"; $(not_a_shell_command)\nSecond line'
        with patch('tavi_providers.claude_command',return_value=['claude.exe']):plan=claude_plan(self.decision(),task,'.',interactive=True)
        self.assertTrue(plan['interactive']);self.assertIsNone(plan['stdin']);self.assertEqual(plan['argv'][-1],task)
        self.assertNotIn('--print',plan['argv']);self.assertEqual(plan['argv'][plan['argv'].index('--permission-mode')+1],'default')

    def test_missing_cli_keeps_an_offline_plan_without_execution(self):
        with patch('tavi_providers.claude_command',return_value=None):plan=claude_plan(self.decision(),'Task','.')
        self.assertFalse(plan['execution_ready']);self.assertEqual(plan['argv'][0],'claude')

    def test_review_request_still_withholds_launch(self):
        data=self.decision();data['status']='needs_review'
        self.assertIsNone(claude_plan(data,'Task','.'))

    def test_skill_instructions_use_portable_words_not_codex_dollar_mentions(self):
        data=self.decision();data['skills']=[dict(name='a-skill',path='C:/skills/a/SKILL.md')]
        with patch('tavi_providers.claude_command',return_value=['claude.exe']):plan=launch_plan(data,'Task','.','claude')
        self.assertIn('a-skill: read C:/skills/a/SKILL.md',plan['stdin']);self.assertNotIn('$a-skill',plan['stdin'])

    def test_status_filters_private_account_fields(self):
        calls=[SimpleNamespace(returncode=0,stdout='2.1.312 (Claude Code)'),SimpleNamespace(returncode=0,stdout=json.dumps(dict(loggedIn=True,authMethod='claude.ai',email='private@example.test',token='private-token')))]
        with patch('tavi_providers.claude_command',return_value=['claude.exe']),patch('tavi_providers.subprocess.run',side_effect=calls):result=claude_status(check_auth=True)
        self.assertTrue(result['authenticated']);self.assertNotIn('private',json.dumps(result));self.assertTrue(result['supported'])

    def test_configured_cjs_entry_uses_node_without_a_shell(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'cli-wrapper.cjs';path.write_text('// fixture')
            with patch('tavi_providers.shutil.which',return_value='node.exe'):
                self.assertEqual(claude_command(path),['node.exe',str(path.resolve())])

    def test_boolean_cli_config_is_rejected(self):
        with self.assertRaises(ValueError):claude_command(True)

if __name__=='__main__':unittest.main()
