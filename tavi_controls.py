"""Resolve exact control facts supplied by a supported host. No capture or input backend."""
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import unicodedata

FORMAT = 'tavi-control-snapshot-v1'
SOURCES = {'supported_browser_dom', 'supported_native'}
ROLES = {'button', 'link', 'tab', 'checkbox', 'switch', 'radio', 'menuitem', 'textbox', 'combobox'}


def normalized(value):
    return ' '.join(unicodedata.normalize('NFC', value).casefold().split())


def _text(value, name, limit=4096):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f'Invalid {name}')
    return value


def _numbers(value, length):
    if not isinstance(value, list) or len(value) != length:
        raise ValueError('Invalid geometry')
    if any(type(n) not in (float, int) or not math.isfinite(n) for n in value):
        raise ValueError('Invalid geometry')
    return value


def resolve(snapshot, task, target, *, role='button', context=None, offline=False, now=None):
    """Return a reviewable identity; data supplied in a file never authorizes input."""
    _text(task, 'task'); _text(target, 'target')
    if role not in ROLES: raise ValueError('Unsupported control role')
    if context is not None: _text(context, 'context')
    if type(offline) is not bool: raise ValueError('offline must be boolean')
    if not isinstance(snapshot, dict) or snapshot.get('format') != FORMAT:
        raise ValueError('Unsupported control snapshot')
    _text(snapshot.get('snapshot_id'), 'snapshot ID', 200)
    if snapshot.get('source') not in SOURCES: raise ValueError('Unsupported snapshot source')
    width, height = _numbers(snapshot.get('viewport'), 2)
    if width <= 0 or height <= 0: raise ValueError('Invalid viewport')
    try:
        captured = datetime.fromisoformat(snapshot['captured_at'].replace('Z', '+00:00'))
    except (KeyError, TypeError, ValueError, AttributeError): raise ValueError('Invalid capture time')
    if captured.tzinfo is None: raise ValueError('Capture time requires a timezone')
    now = now or datetime.now(timezone.utc)
    age = (now - captured).total_seconds()
    controls = snapshot.get('controls')
    if not isinstance(controls, list) or len(controls) > 10000: raise ValueError('Invalid control inventory')
    ids = set(); matches = []; eligible = []
    for c in controls:
        if not isinstance(c, dict): raise ValueError('Invalid control record')
        ident = _text(c.get('id'), 'control ID', 200)
        if ident in ids: raise ValueError('Duplicate control ID')
        ids.add(ident)
        label = _text(c.get('label'), 'control label')
        if c.get('role') not in ROLES: raise ValueError('Unsupported control role')
        if type(c.get('visible')) is not bool or type(c.get('enabled')) is not bool:
            raise ValueError('Control states must be booleans')
        if not isinstance(c.get('context', ''), str): raise ValueError('Invalid control context')
        x, y, w, h = _numbers(c.get('bounds'), 4)
        if w < 0 or h < 0: raise ValueError('Negative control extent')
        if normalized(label) != normalized(target) or c['role'] != role: continue
        if context is not None and normalized(c.get('context', '')) != normalized(context): continue
        matches.append(c)
        if c['visible'] and c['enabled'] and w > 0 and h > 0 and 0 <= x+w/2 < width and 0 <= y+h/2 < height:
            eligible.append(c)
    digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode()).hexdigest()
    result = dict(format='tavi-control-proposal-v1', source=snapshot['source'], snapshot_id=snapshot['snapshot_id'],
                  snapshot_sha256=digest, task_sha256=hashlib.sha256(task.encode()).hexdigest(),
                  target=target, role=role, context=context, probability=None,
                  probability_note='Exact host-supplied control facts; no learned probability.',
                  requires_live_host_check=True, authorization_granted=False, executed_actions=False,
                  offline=offline, age_seconds=round(age, 3), candidate=None, status='review_required')
    if age < -0.5: reason = 'future_snapshot'
    elif not offline and age > 5: reason = 'stale_snapshot'
    elif len(eligible) > 1: reason = 'ambiguous_control'
    elif not matches: reason = 'no_exact_control'
    elif not eligible: reason = 'control_unavailable'
    else:
        c = eligible[0]
        result['candidate'] = {k: c[k] for k in ('id', 'label', 'role', 'bounds')}
        result['candidate']['context'] = c.get('context', '')
        result['status'] = 'offline_match' if offline else 'host_verification_required'
        reason = 'unique_exact_control'
    result['reason'] = reason
    return result


def resolve_file(path, task, target, **options):
    data = Path(path).read_bytes()
    if len(data) > 2_000_000: raise ValueError('Control snapshot exceeds 2MB')
    return resolve(json.loads(data.decode('utf-8-sig')), task, target, **options)
