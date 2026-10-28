"""Bounded public GitHub skill discovery and passive source review. Never installs/runs."""
import base64
import ast
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import urllib.parse
import urllib.request

REPO_PATTERN = r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+'
RISKS = {
 'instruction_override': r'ignore (?:all |any |the )?(?:previous|prior|system) instructions',
 'pipe_to_shell': r'(?:curl|wget|irm|Invoke-WebRequest)[^\n]{0,180}\|\s*(?:sh|bash|iex|Invoke-Expression)',
 'dynamic_execution': r'\b(?:Invoke-Expression|eval\s*\(|exec\s*\()',
 'destructive_command': r'\brm\s+-rf\b|Remove-Item[^\n]*-Recurse',
 'credential_reference': r'(?:API_KEY|ACCESS_TOKEN|SECRET_KEY|auth\.json|credentials)',
}
TEXT_SUFFIXES = {'.md', '.txt', '.py', '.js', '.mjs', '.cjs', '.ts', '.tsx', '.json', '.yaml', '.yml', '.toml', '.sh', '.ps1', '.cmd', '.bat', '.css', '.html', '.svg', '.sql', '.csv'}


def api(endpoint):
    if not endpoint.startswith('/') or '..' in endpoint:
        raise ValueError('Invalid API path')
    request = urllib.request.Request('https://api.github.com'+endpoint,
                                     headers={'User-Agent': 'Tavi-local-skill-review/0.2', 'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(request, timeout=20) as response:
        if urllib.parse.urlsplit(response.url).hostname != 'api.github.com':
            raise ValueError('Unexpected GitHub redirect')
        payload = response.read(8_000_001)
    if len(payload) > 8_000_000:
        raise ValueError('GitHub response exceeds review size limit')
    return json.loads(payload)


def validate_path(path):
    parts = PurePosixPath(path).parts
    if not path or path.startswith('/') or '\\' in path or any(p in ('..', '.') for p in parts):
        raise ValueError('Unsafe repository path')
    reserved = {'con', 'prn', 'aux', 'nul', *(f'com{i}' for i in range(1, 10)), *(f'lpt{i}' for i in range(1, 10))}
    if any(':' in p or p.endswith((' ', '.')) or p.split('.')[0].lower() in reserved for p in parts):
        raise ValueError('Unsafe Windows path')
    return parts


def search(query, limit=5, provider='awesomeskill', installed_names=()):
    if provider == 'awesomeskill':
        from tavi_awesomeskill import search as awesome_search
        return awesome_search(query, limit, installed_names)
    if provider != 'github':
        raise ValueError('Unknown skill discovery provider')
    query = query.strip()
    if not query or len(query) > 160:
        raise ValueError('Search query must contain 1–160 characters')
    query_string = urllib.parse.urlencode({'q': query+' skill in:name,description,readme', 'per_page': min(5, max(1, limit))})
    result = api('/search/repositories?'+query_string)
    return dict(query=query, provider='github', incomplete=result.get('incomplete_results', False),
                repositories=[dict(repo=r['full_name'], url=r['html_url'], description=r.get('description'), archived=r.get('archived', False)) for r in result['items']])


def blob(repo, sha):
    value = api(f'/repos/{repo}/git/blobs/{sha}')
    if value.get('encoding') != 'base64' or value.get('size', 0) > 128_000:
        raise ValueError('Blob unavailable or exceeds per-file review limit')
    payload = base64.b64decode(value['content'])
    if hashlib.sha1(b'blob '+str(len(payload)).encode()+b'\0'+payload).hexdigest() != sha:
        raise ValueError('Git blob integrity mismatch')
    return payload


def review(repo, skill_path, task, model, installed_names=(), stage=None, ref=None):
    if not re.fullmatch(REPO_PATTERN, repo):
        raise ValueError('Repository must be owner/name')
    if not skill_path.endswith('SKILL.md'):
        raise ValueError('Skill path must end in SKILL.md')
    validate_path(skill_path)
    info = api('/repos/'+repo)
    ref = ref or info['default_branch']
    commit = api(f'/repos/{repo}/commits/'+urllib.parse.quote(ref, safe=''))['sha']
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('Invalid pinned commit')
    tree = api(f'/repos/{repo}/git/trees/{commit}?recursive=1')
    if tree.get('truncated'):
        raise ValueError('Repository tree is incomplete; cannot claim complete review')
    entries = {item['path']: item for item in tree['tree']}
    if skill_path not in entries:
        options = [p for p in entries if p.endswith('/SKILL.md') or p == 'SKILL.md']
        raise ValueError('Skill path absent. Available paths: '+', '.join(options[:20]))
    prefix = skill_path[:-len('SKILL.md')]
    files = [item for path, item in entries.items() if path.startswith(prefix) and item['type'] != 'tree']
    if len(files) > 40 or sum(item.get('size', 0) for item in files) > 512_000:
        raise ValueError('Skill exceeds bounded complete-review budget (40 files / 512 KB)')
    fetched = {}
    findings = []
    casefold_paths = set()
    for item in files:
        relative = item['path'][len(prefix):]
        validate_path(relative)
        if relative.lower() in casefold_paths:
            raise ValueError('Case-insensitive duplicate source paths')
        casefold_paths.add(relative.lower())
        if item.get('mode') not in ('100644', '100755') or item['type'] != 'blob':
            raise ValueError('Symlink or submodule cannot be staged as a reviewed skill')
        if Path(relative).suffix.lower() not in TEXT_SUFFIXES and Path(relative).name.upper() not in ('LICENSE', 'NOTICE', 'MAKEFILE'):
            raise ValueError('Unreviewed binary or unsupported file type: '+relative)
        payload = blob(repo, item['sha'])
        text = payload.decode('utf-8-sig')
        fetched[relative] = payload
        for label, pattern in RISKS.items():
            if re.search(pattern, text, re.I):
                findings.append(dict(file=relative, finding=label))
    skill_text = fetched['SKILL.md'].decode('utf-8-sig')
    match = re.search(r'^name:\s*[\"\']?([^\r\n\"\']+)', skill_text, re.M)
    name = match[1].strip() if match else Path(prefix.rstrip('/')).name
    licence = (info.get('license') or {}).get('spdx_id')
    skill_licenses = {p: hashlib.sha256(b).hexdigest() for p,b in fetched.items() if Path(p).name.upper() in ('LICENSE', 'LICENSE.TXT', 'LICENSE.MD', 'COPYING')}
    dependency_hints = set()
    runtimes = set()
    for path, payload in fetched.items():
        suffix = Path(path).suffix.lower()
        if suffix == '.py':
            runtimes.add('python')
            try:
                syntax = ast.parse(payload.decode('utf-8-sig'))
                for node in ast.walk(syntax):
                    names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module] if isinstance(node, ast.ImportFrom) else []
                    for dependency_name in names:
                        if dependency_name and dependency_name.split('.')[0] not in sys.stdlib_module_names:
                            dependency_hints.add(dependency_name.split('.')[0])
            except SyntaxError:
                findings.append(dict(file=path, finding='python_parse_failure'))
        elif suffix in ('.js', '.mjs', '.cjs', '.ts', '.tsx'):
            runtimes.add('node')
        elif suffix in ('.sh',):
            runtimes.add('bash')
        elif suffix == '.ps1':
            runtimes.add('powershell')
    license_files = [p for p in entries if p.upper() in ('LICENSE', 'LICENSE.MD', 'LICENSE.TXT', 'COPYING')]
    license_hashes = {}
    for path in license_files[:2]:
        license_hashes[path] = hashlib.sha256(blob(repo, entries[path]['sha'])).hexdigest()
    query_terms = set(re.findall(r'[a-z]{4,}', task.lower()))
    candidate_terms = set(re.findall(r'[a-z]{4,}', skill_text[:6000].lower()))
    shared = sorted(query_terms & candidate_terms)
    prediction = model.infer(task)
    duplicate = name in installed_names
    if duplicate:
        recommendation = 'skip_duplicate'
    elif findings or ((not licence or licence == 'NOASSERTION') and not skill_licenses) or not shared:
        recommendation = 'review_required'
    else:
        recommendation = 'download_for_review'
    report = dict(repo=repo, commit=commit, skill_path=skill_path, name=name,
                  source_url=f'https://github.com/{repo}/tree/{commit}/{prefix.rstrip("/")}',
                  license=licence, license_files=license_hashes, skill_license_files=skill_licenses, duplicate=duplicate,
                  shared_task_terms=shared, learned_external_score=prediction['external_score'],
                  findings=findings, recommendation=recommendation, installation_authorized=False,
                  compatibility='SKILL.md present; dependencies and runtime compatibility require human/host validation',
                  dependency_hints=sorted(dependency_hints), runtimes={r: bool(shutil.which(r)) for r in sorted(runtimes)},
                  limits='Static pattern review is not a malware, instruction-safety or licence compatibility guarantee.',
                  files=[dict(path=p, bytes=len(b), sha256=hashlib.sha256(b).hexdigest()) for p,b in fetched.items()])
    if stage is not None:
        if 'tavi-review.json' in casefold_paths:
            raise ValueError('Skill contains reserved staging report filename')
        root = Path(stage).resolve()
        # Create a new review directory; never overwrite or activate a host skill.
        if root.exists():
            raise ValueError('Staging directory already exists; choose a new directory')
        root.mkdir(parents=True)
        for path, payload in fetched.items():
            destination = root.joinpath(*validate_path(path))
            if not destination.resolve().is_relative_to(root):
                raise ValueError('Staging path escaped review directory')
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open('xb') as output:
                output.write(payload)
        (root/'tavi-review.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        report['staged_at'] = str(root)
    return report
