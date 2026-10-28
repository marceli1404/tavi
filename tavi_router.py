"""Apply Tavi's learned decisions to the current host inventory."""
from datetime import datetime, timezone
import re
import uuid
from tavi_model import DecisionModel

DEFAULT_ROLES = {'fast': ['gpt-6-luna', 'gpt-6.1-sol'], 'balanced': ['gpt-6.1-sol', 'gpt-6-sol'],
                 'deep': ['gpt-6-astra', 'gpt-6.1-sol']}


def route_custom(prompt, skills, models, model, requested_model=None, requested_skills=(), roles=None, policy=None,
                 preference='auto', excluded_models=(), excluded_skills=()):
    if not prompt.strip() or len(prompt) > 16000:
        raise ValueError('Task must contain 1–16000 characters')
    catalog = {m['id']: m for m in models}
    if requested_model and requested_model not in catalog:
        raise ValueError('Requested model is not in the visible Codex catalog')
    if preference not in ('auto', 'speed', 'quality'):
        raise ValueError('Preference must be auto, speed or quality')
    unknown_exclusions = set(excluded_models) - set(catalog)
    if unknown_exclusions:
        raise ValueError('Excluded model not in visible catalog: '+', '.join(sorted(unknown_exclusions)))
    if requested_model in excluded_models:
        raise ValueError('Explicit model conflicts with model exclusion')
    skill_identifiers = {s['id'] for s in skills} | {s['name'] for s in skills}
    unknown_skill_exclusions = set(excluded_skills) - skill_identifiers
    if unknown_skill_exclusions:
        raise ValueError('Excluded skill not in installed inventory: '+', '.join(sorted(unknown_skill_exclusions)))
    result = dict(version='0.3.0', decision_id=str(uuid.uuid4()), timestamp=datetime.now(timezone.utc).isoformat(),
                  backend='tavi-neural-cpu', model_artifact=model.metadata['weights_sha256'], status='needs_review',
                  model=None, skills=[], candidates=[], warnings=[],
                  inventory=dict(models=len(models), skills=len(skills), catalog_scope='CLI-visible, not verified inference entitlement'))
    prediction = model.infer(prompt)
    result['prediction'] = {k:v for k,v in prediction.items() if k != 'skills'}
    by_name = {}
    for skill in skills:
        by_name.setdefault(skill['name'], []).append(skill)
    added = set()

    def add_skill(skill, selection, score=None):
        if skill['name'] in excluded_skills or skill['id'] in excluded_skills:
            if selection in ('required-policy', 'explicit'):
                raise ValueError('Skill exclusion conflicts with explicit/required skill: '+skill['name'])
            return
        if skill['id'] not in added:
            result['skills'].append(dict(**skill, selection=selection, score=score))
            added.add(skill['id'])

    for ident in requested_skills:
        matches = [s for s in skills if s['id'] == ident or s['name'] == ident]
        if len(matches) != 1:
            raise ValueError(f'Explicit skill must identify exactly one installed skill: {ident}')
        add_skill(matches[0], 'explicit')
    # A small host policy layer enforces user requirements separately from learned weights.
    # It is deliberately visible in output; this is not claimed as learned behaviour.
    policy = policy or {}
    for name in policy.get('always_skills', []):
        if name in by_name:
            add_skill(by_name[name][0], 'required-policy')
        else:
            result['warnings'].append('Required policy skill unavailable: '+name)
    for rule in policy.get('rules', []):
        if re.search(rule['pattern'], prompt, re.I):
            for name in rule['skills']:
                if name in by_name:
                    add_skill(by_name[name][0], 'required-policy')
                else:
                    result['warnings'].append('Required policy skill unavailable: '+name)
    if requested_model:
        chosen = requested_model
        source = 'explicit'
    else:
        chosen = None
        source = 'learned-tier-policy-map'
        tier = prediction['tier']
        if tier != 'review' and prediction['vocabulary_coverage'] >= .15 and max(prediction['tier_scores'].values()) >= .5:
            role = {'speed': 'fast', 'quality': 'deep'}.get(preference, tier)
            chosen = next((m for m in (roles or DEFAULT_ROLES).get(role, []) if m in catalog and m not in excluded_models), None)
            if role != tier:
                source = 'explicit-preference-policy-map'
    if chosen:
        entry = catalog[chosen]
        effective_tier = prediction['tier'] if requested_model else {'speed':'fast', 'quality':'deep'}.get(preference, prediction['tier'])
        desired = {'fast': 'low', 'balanced': 'medium', 'deep': 'high'}.get(effective_tier, entry['default_effort'])
        effort = desired if desired in entry.get('efforts', []) else entry['default_effort']
        result['model'] = dict(id=chosen, reasoning=effort, selection=source,
                               score=max(prediction['tier_scores'].values()) if source == 'learned-tier-policy-map' else None)
        result['status'] = 'recommended'
    else:
        result['warnings'].append('Task is ambiguous, outside known vocabulary, or no configured role model is available.')
    for item in prediction['skills'][:8]:
        result['candidates'].append(item)
    for item in prediction['skills'][:3]:
        matches = by_name.get(item['name'], [])
        if item['score'] >= prediction['skill_threshold'] and matches:
            if len(matches) == 1:
                add_skill(matches[0], 'learned', item['score'])
            else:
                result['warnings'].append('Ambiguous learned skill name needs explicit ID: '+item['name'])
    pinned_names = {s['name'] for s in result['skills'] if s['selection'] == 'required-policy'}
    external = prediction['external_score'] >= prediction['external_threshold']
    missing = [s for s in prediction['skills'][:3] if s['score'] >= prediction['skill_threshold'] and s['name'] not in by_name]
    result['discovery'] = dict(status='search_recommended' if external or missing else 'not_needed',
                               score=prediction['external_score'], missing_skills=[s['name'] for s in missing],
                               installation_authorized=False)
    if external or missing:
        from tavi_awesomeskill import search_url
        query = prompt[:160]
        result['discovery'].update(suggested_query=query, provider='awesomeskill',
                                   source_selection='user-preference-policy',
                                   search_url=search_url(query),
                                   next_step='Run discover, then review the pinned upstream source before downloading a skill.')
    result['policy_skills'] = sorted(pinned_names)
    result['explanation'] = dict(learned_tier=prediction['tier'], preference=preference,
                               model_selection=result['model']['selection'] if result['model'] else 'withheld',
                               excluded_models=list(excluded_models), excluded_skills=list(excluded_skills),
                               learned_skills=[s['name'] for s in result['skills'] if s['selection'] == 'learned'],
                               required_skills=sorted(pinned_names), vocabulary_coverage=prediction['vocabulary_coverage'])
    if any(w.startswith('Required policy skill unavailable:') for w in result['warnings']):
        result['status'] = 'needs_review'
    result['warnings'].append('Synthetic-policy model: scores are not calibrated real-world success probabilities. Model IDs are mapped from a learned workload tier, not benchmarked model performance.')
    return result
