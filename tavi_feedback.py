"""Append-only local feedback events; no automatic model mutation."""
import json
from pathlib import Path
import uuid
from datetime import datetime, timezone


def save_feedback(base, decision_id, tier, skill_names, external, outcome, evidence):
    ident = str(uuid.UUID(decision_id))
    source = Path(base)/'data/decisions'/f'{ident}.json'
    record = json.loads(source.read_text(encoding='utf-8'))
    if tier not in ('fast', 'balanced', 'deep', 'review'):
        raise ValueError('Invalid workload tier')
    if outcome not in ('success', 'failure', 'unverified'):
        raise ValueError('Invalid outcome')
    if not evidence.strip():
        raise ValueError('A feedback observation or evidence note is required')
    event = dict(id=str(uuid.uuid4()), decision_id=ident, timestamp=datetime.now(timezone.utc).isoformat(),
                 prompt=record['prompt'], tier=tier, skills=skill_names, external=bool(external),
                 outcome=outcome, evidence=evidence, origin='operator-entered-feedback', split='train')
    directory = Path(base)/'data/feedback'
    directory.mkdir(parents=True, exist_ok=True)
    with (directory/(event['id']+'.json')).open('x', encoding='utf-8') as stream:
        json.dump(event, stream, indent=2)
    return event
