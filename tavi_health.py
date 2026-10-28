"""Inventory drift, isolated CPU refresh, and optimistic model activation."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid


def inventory_health(model, skills, model_dir):
    learned = set(model.metadata['skills'])
    current = {s['name'] for s in skills}
    dataset_path = Path(model_dir)/'dataset.json'
    trained = {}
    if dataset_path.is_file():
        for row in json.loads(dataset_path.read_text(encoding='utf-8')):
            if row.get('origin') == 'weak-skill-metadata':
                for name in row['skills']:
                    trained.setdefault(name, set()).add(row['prompt'])
    changed = sorted({s['name'] for s in skills if s['name'] in learned and trained.get(s['name'])
                      and s['name'].replace('-', ' ')+' '+s['description'] not in trained[s['name']]})
    report = dict(learned_skill_names=len(learned), installed_skill_names=len(current),
                  new_skills=sorted(current-learned), removed_skills=sorted(learned-current),
                  changed_skills=changed, metadata_comparison_available=bool(trained))
    branches = model.metadata.get('extensions', [model.metadata['extension']] if model.metadata.get('extension') else [])
    report['unvalidated_skills'] = sorted({v['name'] for b in branches for v in b['validation'] if not v['ready']})
    report['status'] = 'needs_refresh' if report['new_skills'] or report['removed_skills'] or changed else 'current'
    if report['unvalidated_skills'] and report['status'] == 'current':
        report['status'] = 'needs_validation'
    return report


def activate_candidate(config_path, expected_bytes, candidate, accepted_report):
    """Keep a recoverable config snapshot and refuse stale or failed promotions."""
    config_path = Path(config_path).resolve()
    if not accepted_report.get('passed'):
        raise ValueError('Candidate did not pass evaluation; activation refused')
    from tavi_model import DecisionModel
    loaded = DecisionModel.load(candidate)
    if accepted_report.get('weights_sha256') != loaded.metadata['weights_sha256']:
        raise ValueError('Evaluation is not for these candidate weights')
    if config_path.read_bytes() != expected_bytes:
        raise RuntimeError('Config changed during refresh; candidate retained, activation refused')
    previous = json.loads(expected_bytes.decode('utf-8-sig'))
    snapshot = Path(candidate)/'previous-config.json'
    with snapshot.open('xb') as stream:
        stream.write(expected_bytes)
    next_config = dict(previous, model_path=str(Path(candidate).resolve()))
    temp = config_path.with_name(config_path.name+'.'+uuid.uuid4().hex+'.tmp')
    with temp.open('x', encoding='utf-8') as stream:
        json.dump(next_config, stream, indent=2)
    # An external editor need not respect a lock: check again immediately before replace.
    if config_path.read_bytes() != expected_bytes:
        temp.unlink()
        raise RuntimeError('Config changed during activation; candidate and snapshot retained')
    os.replace(temp, config_path)
    return dict(active_model=str(Path(candidate).resolve()), previous_model=previous.get('model_path'),
                previous_config_snapshot=str(snapshot))


def rollback(config_path, base):
    config_path = Path(config_path).resolve()
    expected = config_path.read_bytes()
    current = json.loads(expected.decode('utf-8-sig'))
    active = model_location(current, config_path, base)
    snapshot = active/'previous-config.json'
    if not snapshot.is_file():
        raise ValueError('Active model has no previous-config snapshot to roll back to')
    previous = json.loads(snapshot.read_text(encoding='utf-8-sig'))
    previous_path = model_location(previous, config_path, base)
    from tavi_model import DecisionModel
    DecisionModel.load(previous_path)
    replacement = dict(current, model_path=str(previous_path))
    temp = config_path.with_name(config_path.name+'.'+uuid.uuid4().hex+'.tmp')
    with temp.open('x', encoding='utf-8') as stream:
        json.dump(replacement, stream, indent=2)
    if config_path.read_bytes() != expected:
        temp.unlink()
        raise RuntimeError('Config changed during rollback; rollback refused')
    os.replace(temp, config_path)
    result = dict(previous_active_model=str(active), active_model=str(previous_path),
                  preserved_other_config=True, timestamp=datetime.now(timezone.utc).isoformat())
    log_dir = Path(base)/'output/rollbacks'
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir/(uuid.uuid4().hex+'.json')).write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


def refresh(base, config_path, activate=False, strategy='auto'):
    base, config_path = Path(base).resolve(), Path(config_path).resolve()
    original = config_path.read_bytes()
    config = json.loads(original.decode('utf-8-sig'))
    current_model = model_location(config, config_path, base)
    from tavi_model import DecisionModel
    from tavi import scan_skills
    current = DecisionModel.load(current_model)
    health = inventory_health(current,scan_skills(config['skill_roots']),current_model)
    if strategy not in ('auto','expand','full'):
        raise ValueError('Unknown refresh strategy')
    if strategy == 'auto' and health['status'] == 'current':
        return dict(status='current', activated=False, candidate=None, previous_model=str(current_model), catalog=health)
    can_expand = bool(health['new_skills']) and not health['changed_skills'] and not health['removed_skills']
    if strategy == 'expand' and not can_expand:
        raise ValueError('Expansion requires new names and unchanged existing skill metadata; use full refresh for other changes')
    chosen_strategy = 'expand' if strategy == 'expand' or (strategy == 'auto' and can_expand) else 'full'
    candidate = base/'models'/('tavi-refresh-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:6])
    # Pass an immutable config snapshot to training; do not race a changing live config.
    snapshots = base/'output/refresh-inputs'
    snapshots.mkdir(parents=True, exist_ok=True)
    frozen = snapshots/(candidate.name+'.json')
    frozen.write_bytes(original)
    result = dict(candidate=str(candidate), previous_model=str(current_model), activated=False, strategy=chosen_strategy,
                  config_sha256=hashlib.sha256(original).hexdigest())
    train_command = [sys.executable,str(base/('expand_tavi.py' if chosen_strategy=='expand' else 'train_tavi.py')),
                     '--config',str(frozen),'--output',str(candidate)]
    if chosen_strategy == 'expand':
        train_command += ['--base',str(current_model)]
    steps = [('training',train_command),('evaluation',[sys.executable,str(base/'evaluate_tavi.py'),'--model',str(candidate)])]
    check_added_skills = chosen_strategy == 'expand' or 'tavi-decision' in current.metadata['skills']
    if check_added_skills:
        added_command = [sys.executable,str(base/'evaluate_expansion.py'),'--base',str(current_model),'--model',str(candidate)]
        if chosen_strategy == 'full':
            added_command.append('--allow-base-change')
        steps.append(('extension-evaluation',added_command))
    for step, command in steps:
        proc = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', timeout=180, cwd=base)
        candidate.mkdir(parents=True, exist_ok=True)
        (candidate/(step+'.log')).write_text(proc.stdout+'\n'+proc.stderr, encoding='utf-8')
        if proc.returncode:
            result.update(status=step+'_failed', log=str(candidate/(step+'.log')))
            (candidate/'refresh-report.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
            return result
    report = json.loads((candidate/'evaluation.json').read_text(encoding='utf-8'))
    if check_added_skills:
        extra_report = json.loads((candidate/'extension-evaluation.json').read_text(encoding='utf-8'))
        result['extension_acceptance'] = {k:v for k,v in extra_report.items() if k != 'results'}
        if not extra_report['passed']:
            report['passed'] = False
    baseline_path = current_model/'evaluation.json'
    if baseline_path.is_file():
        baseline = json.loads(baseline_path.read_text(encoding='utf-8'))
        keys = ('tier_accuracy', 'skill_recall_at_3', 'external_accuracy', 'skill_precision', 'skill_recall', 'no_skill_accuracy')
        regressions = [k for k in keys if report['metrics'][k] < baseline['metrics'][k]-.02]
        result['regressions'] = regressions
        if regressions:
            report['passed'] = False
    result.update(status='accepted' if report['passed'] else 'evaluation_failed', metrics=report['metrics'])
    if activate and report['passed']:
        try:
            result['activation'] = activate_candidate(config_path, original, candidate, report)
            result['activated'] = True
        except (ValueError, RuntimeError, OSError) as error:
            result.update(status='activation_refused', error=str(error))
    (candidate/'refresh-report.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result
def model_location(config, config_path, base):
    value = config.get('model_path')
    if value is None:
        return bundled_model(base)
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (Path(config_path).resolve().parent/path).resolve()


def bundled_model(base):
    root = Path(base).resolve()/'models'
    pointer = root/'default-model.json'
    if not pointer.is_file():
        return root/'tavi-v1'
    path = (root/json.loads(pointer.read_text(encoding='utf-8'))['path']).resolve()
    if not path.is_relative_to(root):
        raise ValueError('Bundled model pointer escapes the model directory')
    return path


