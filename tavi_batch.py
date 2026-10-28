"""Bounded per-item batch routing; never launches tasks or calls external inference."""
import json
from pathlib import Path
from tavi_router import route_custom


def read_tasks(path):
    path = Path(path)
    if path.stat().st_size > 1_000_000:
        raise ValueError('Batch input exceeds 1 MB')
    tasks = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= 256:
        raise ValueError('Batch input must be an array of 1–256 tasks')
    return tasks


def route_batch(tasks, skills, models, model, roles=None, policy=None, preference='auto'):
    results = []
    seen = set()
    for index, item in enumerate(tasks):
        ident = str(index+1)
        try:
            if isinstance(item, str):
                item = {'prompt':item}
            if not isinstance(item, dict):
                raise ValueError('Task must be a string or object')
            unknown = set(item) - {'id','prompt','model','skills','preference','exclude_models','exclude_skills'}
            if unknown:
                raise ValueError('Unsupported batch fields: '+', '.join(sorted(unknown)))
            ident = str(item.get('id', ident))
            if ident in seen:
                raise ValueError('Duplicate batch task ID')
            seen.add(ident)
            if not isinstance(item.get('prompt'), str):
                raise ValueError('Task prompt must be a string')
            for key in ('skills', 'exclude_models', 'exclude_skills'):
                value = item.get(key, [])
                if not isinstance(value, list) or not all(isinstance(v,str) for v in value):
                    raise ValueError(key+' must be an array of strings')
            decision = route_custom(item['prompt'], skills, models, model, item.get('model'), item.get('skills', []),
                                    roles, policy, item.get('preference', preference), item.get('exclude_models', []), item.get('exclude_skills', []))
            results.append(dict(index=index+1, id=ident, decision=decision))
        except (ValueError, TypeError, KeyError) as error:
            results.append(dict(index=index+1, id=ident, error=str(error)))
    return dict(tasks=len(results), errors=sum('error' in r for r in results),
                needs_review=sum(r.get('decision',{}).get('status') == 'needs_review' for r in results), results=results,
                executed=False)
