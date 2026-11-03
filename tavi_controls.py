"""Resolve exact control facts supplied by a supported host. No capture or input backend."""
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import unicodedata
from types import MappingProxyType

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


def _query(task, target, role, context, offline):
    _text(task, 'task'); _text(target, 'target')
    if role not in ROLES: raise ValueError('Unsupported control role')
    if context is not None: _text(context, 'context')
    if type(offline) is not bool: raise ValueError('offline must be boolean')


class ControlIndex:
    """Copied single-observation facts; queries never imply live control trust."""
    __slots__ = ('_by_role','_by_context','_context_indexed','_captured','_source','_snapshot_id','_snapshot_sha256')

    @property
    def snapshot_sha256(self):
        return self._snapshot_sha256

    def __init__(self, snapshot, *, context_index=True):
        if type(context_index) is not bool: raise ValueError('context_index must be boolean')
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
        controls = snapshot.get('controls')
        if not isinstance(controls, list) or len(controls) > 10000: raise ValueError('Invalid control inventory')
        ids = set(); by_role = {}; by_context = {}
        for c in controls:
            if not isinstance(c, dict): raise ValueError('Invalid control record')
            ident = _text(c.get('id'), 'control ID', 200)
            if ident in ids: raise ValueError('Duplicate control ID')
            ids.add(ident)
            label = _text(c.get('label'), 'control label')
            if c.get('role') not in ROLES: raise ValueError('Unsupported control role')
            if type(c.get('visible')) is not bool or type(c.get('enabled')) is not bool:
                raise ValueError('Control states must be booleans')
            context = c.get('context', '')
            if not isinstance(context, str): raise ValueError('Invalid control context')
            x, y, w, h = _numbers(c.get('bounds'), 4)
            if w < 0 or h < 0: raise ValueError('Negative control extent')
            eligible = c['visible'] and c['enabled'] and w > 0 and h > 0 and 0 <= x+w/2 < width and 0 <= y+h/2 < height
            # Tuples copy every value used in proposals. Neither the caller's
            # inventory nor a returned candidate can mutate this observation.
            record = (ident, label, c['role'], (x,y,w,h), context, eligible)
            key = (normalized(label), c['role'])
            by_role.setdefault(key, []).append(record)
            if context_index:
                by_context.setdefault((*key,normalized(context)), []).append(record)
        self._by_role = MappingProxyType({k:tuple(v) for k,v in by_role.items()})
        self._by_context = MappingProxyType({k:tuple(v) for k,v in by_context.items()})
        self._context_indexed = context_index
        self._captured = captured
        self._source = snapshot['source']; self._snapshot_id = snapshot['snapshot_id']
        self._snapshot_sha256 = hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=False,
            allow_nan=False, separators=(',', ':')).encode()).hexdigest()

    def resolve(self, task, target, *, role='button', context=None, offline=False, now=None):
        _query(task, target, role, context, offline)
        if context is not None and not self._context_indexed:
            raise ValueError('This prepared index cannot resolve context-scoped queries')
        # A prepared index does not reset freshness or skip future-clock checks.
        age = ((now or datetime.now(timezone.utc))-self._captured).total_seconds()
        key = (normalized(target), role)
        matches = (self._by_role.get(key, ()) if context is None else
                   self._by_context.get((*key,normalized(context)), ()))
        eligible = [c for c in matches if c[5]]
        result = dict(format='tavi-control-proposal-v1', source=self._source, snapshot_id=self._snapshot_id,
            snapshot_sha256=self.snapshot_sha256, task_sha256=hashlib.sha256(task.encode()).hexdigest(),
            target=target, role=role, context=context, probability=None,
            probability_note='Exact host-supplied control facts; no learned probability.',
            requires_live_host_check=True, authorization_granted=False, executed_actions=False,
            offline=offline, age_seconds=round(age,3), candidate=None, status='review_required')
        if age < -0.5: reason = 'future_snapshot'
        elif not offline and age > 5: reason = 'stale_snapshot'
        elif len(eligible) > 1: reason = 'ambiguous_control'
        elif not matches: reason = 'no_exact_control'
        elif not eligible: reason = 'control_unavailable'
        else:
            c = eligible[0]
            result['candidate'] = dict(id=c[0],label=c[1],role=c[2],bounds=list(c[3]),context=c[4])
            result['status'] = 'offline_match' if offline else 'host_verification_required'
            reason = 'unique_exact_control'
        result['reason'] = reason
        return result


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
        result['candidate'] = {k: c[k] for k in ('id', 'label', 'role')}
        result['candidate']['bounds'] = list(c['bounds'])
        result['candidate']['context'] = c.get('context', '')
        result['status'] = 'offline_match' if offline else 'host_verification_required'
        reason = 'unique_exact_control'
    result['reason'] = reason
    return result


def _read(path):
    data = Path(path).read_bytes()
    if len(data) > 2_000_000: raise ValueError('Control file exceeds2MB')
    return json.loads(data.decode('utf-8-sig'))


def resolve_file(path, task, target, **options):
    return resolve(_read(path),task,target,**options)


def resolve_many(snapshot, queries, *, offline=False, now=None):
    """Resolve bounded independent queries from one observation; never execute."""
    if not isinstance(queries,list) or not 1 <= len(queries) <= 1000:
        raise ValueError('Provide 1-1000 control queries')
    ids = set()
    for q in queries:
        if not isinstance(q,dict) or not {'task','target'} <= set(q) or set(q)-{'id','task','target','role','context'}:
            raise ValueError('Invalid control query')
        if 'id' in q:
            _text(q['id'],'query ID',200)
            if q['id'] in ids: raise ValueError('Duplicate query ID')
            ids.add(q['id'])
        _query(q['task'],q['target'],q.get('role','button'),q.get('context'),offline)
    # Skip the *unused* context index for unscoped batch lookups. Full
    # snapshot validation and canonical SHA-256 binding remain unchanged.
    index = ControlIndex(snapshot, context_index=any(q.get('context') is not None for q in queries))
    # Preserve per-query freshness checks: each proposal must independently
    # detect expiry even if a batch crosses the five-second staleness limit.
    proposals = []
    for q in queries:
        result = index.resolve(q['task'],q['target'],role=q.get('role','button'),context=q.get('context'),offline=offline,now=now)
        if 'id' in q: result['query_id'] = q['id']
        proposals.append(result)
    return dict(format='tavi-control-batch-v1',snapshot_sha256=index.snapshot_sha256,proposals=proposals,
                requires_live_host_check=True,authorization_granted=False,executed_actions=False)


def resolve_many_files(snapshot, queries, **options):
    return resolve_many(_read(snapshot),_read(queries),**options)
