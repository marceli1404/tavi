"""Provider-specific CLI plans. Aliases are policy, not measured model rankings."""
from pathlib import Path
import json
import os
import re
import shutil
import subprocess

CLAUDE_ROLES={'fast':['haiku'],'balanced':['sonnet'],'deep':['opus']}


def claude_catalog():
    return [dict(id='haiku',description='Claude Code Haiku alias; account access not verified',efforts=[],default_effort='provider-default'),
            dict(id='sonnet',description='Claude Code Sonnet alias; account access not verified',efforts=['low','medium','high'],default_effort='medium'),
            dict(id='opus',description='Claude Code Opus alias; account access not verified',efforts=['low','medium','high'],default_effort='high')]


def claude_command(configured=None):
    if configured is not None:
        if not isinstance(configured,(str,os.PathLike)):raise ValueError('claude_cli must be an executable or JS entrypoint path')
        path=Path(configured).expanduser().resolve()
        if not path.is_file():raise ValueError('Configured Claude CLI does not exist')
        if path.suffix.lower() in ('.js','.cjs','.mjs'):
            node=shutil.which('node')
            if not node:raise RuntimeError('Node is required for the configured Claude CLI')
            return [node,str(path)]
        binary=str(path)
    else:binary=shutil.which('claude') or shutil.which('claude.cmd')
    if not binary:
        standard=Path.home()/'.local/bin/claude.exe'
        if standard.is_file():binary=str(standard)
    if not binary:return None
    if os.name=='nt' and Path(binary).suffix.lower() in ('.cmd','.bat','.ps1'):
        package=Path(binary).parent/'node_modules/@anthropic-ai/claude-code'
        entry=next((package/name for name in ('cli-wrapper.cjs','cli.js') if (package/name).is_file()),None)
        if entry is None:return None
        node=shutil.which('node')
        return [node,str(entry)] if node else None
    return [binary]


def claude_status(configured=None,check_auth=False):
    command=claude_command(configured)
    result=dict(provider='claude',available=command is not None,version=None,authenticated=None,
                auth_checked=False,model_entitlement_verified=False)
    if not command:return result
    version=subprocess.run(command+['--version'],capture_output=True,text=True,encoding='utf-8',timeout=15)
    match=re.search(r'\b(\d+)\.(\d+)\.(\d+)\b',version.stdout)
    if version.returncode or not match:raise RuntimeError('Claude CLI version check failed')
    result['version']='.'.join(match.groups());result['supported']=tuple(map(int,match.groups()))>=(2,1,259)
    if check_auth:
        auth=subprocess.run(command+['auth','status'],capture_output=True,text=True,encoding='utf-8',timeout=20)
        try:data=json.loads(auth.stdout)
        except ValueError:raise RuntimeError('Claude authentication status is unavailable')
        # Do not expose emails, account identifiers, tokens or configuration paths.
        result.update(auth_checked=True,authenticated=data.get('loggedIn') is True,auth_method=data.get('authMethod','unknown'))
    return result


def provider_roles(provider,config):
    return config.get('claude_model_roles',CLAUDE_ROLES) if provider=='claude' else config.get('model_roles')


def claude_plan(decision,task,workspace,*,interactive=False,configured=None):
    if decision['status']!='recommended' or not decision.get('model'):return None
    executable=claude_command(configured);chosen=decision['model'];effort=chosen.get('reasoning')
    if interactive:
        argv=(executable or ['claude'])+['--model',chosen['id'],'--permission-mode','default']
        if effort in ('low','medium','high'):argv+=['--effort',effort]
        argv+=[task]
        return dict(provider='claude',argv=argv,stdin=None,cwd=str(Path(workspace).resolve()),executed=False,interactive=True,
                    execution_ready=executable is not None,permission_scope='Native interactive Claude Code permissions; user controls tool and edit approvals',
                    requirements='Claude Code installed and authenticated; run this handoff from an interactive terminal.')
    argv=(executable or ['claude'])+['--print','--model',chosen['id'],'--permission-mode','plan',
        '--tools','Read,Glob,Grep','--disallowedTools','mcp__*','--permission-prompts','none',
        '--no-session-persistence','--output-format','json','--setting-sources','']
    if effort in ('low','medium','high'):argv+=['--effort',effort]
    return dict(provider='claude',argv=argv,stdin=task,cwd=str(Path(workspace).resolve()),executed=False,
                execution_ready=executable is not None,permission_scope='Model tools limited to planning/read/search; no shell, edits or MCP tools. CLI managed policies still apply; not an OS sandbox.',
                requirements='Claude Code 2.1.259+ installed and separately authenticated; aliases depend on the account/provider.')
