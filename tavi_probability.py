"""Probability semantics and optional held-out temperature calibration."""
import hashlib
import json
import math
import re
import numpy as np

TIERS = ['fast', 'balanced', 'deep', 'review']


def signature(metadata):
    return hashlib.sha256(json.dumps(metadata, sort_keys=True).encode()).hexdigest()


def temperature_probabilities(probabilities, temperature):
    p = np.clip(np.asarray(probabilities, dtype=np.float64), 1e-12, 1)
    logits = np.log(p)/temperature
    logits -= logits.max(axis=-1, keepdims=True)
    p = np.exp(logits)
    return p/p.sum(axis=-1, keepdims=True)


def binary_temperature(probabilities, temperature):
    p = np.clip(np.asarray(probabilities, dtype=np.float64), 1e-12, 1-1e-12)
    z = np.log(p/(1-p))/temperature
    return 1/(1+np.exp(-np.clip(z, -40, 40)))


def validate_calibration(calibration, metadata):
    if calibration.get('format') != 'tavi-probability-v1' or calibration.get('model_signature') != signature(metadata):
        raise ValueError('Probability calibration does not match this model')
    if calibration.get('accepted') is not True:
        raise ValueError('Probability calibration has not passed its validation gates')
    for key in ('tier_temperature', 'external_temperature'):
        value = calibration.get(key)
        if type(value) not in (int, float) or not math.isfinite(value) or not .05 <= value <= 100:
            raise ValueError('Invalid probability calibration temperature')
    heads=calibration.get('head_acceptance')
    if heads is not None:
        if set(heads)!={'tier','external'} or not all(type(v) is bool for v in heads.values()) or not any(heads.values()):
            raise ValueError('Invalid per-head calibration status')
        for head in heads:
            if not heads[head] and calibration[head+'_temperature']!=1:
                raise ValueError('Rejected calibration head must retain raw scores')
    contexts=calibration.get('context_acceptance')
    if contexts is not None:
        if not contexts or not set(contexts)<={'plain_text','python_spec'}:
            raise ValueError('Invalid calibration contexts')
        for values in contexts.values():
            if set(values)!={'tier','external'} or not all(type(v) is bool for v in values.values()):
                raise ValueError('Invalid context calibration status')
        if heads is None or any(heads[h]!=any(v[h] for v in contexts.values()) for h in heads):
            raise ValueError('Inconsistent calibration context/head status')


def summarize(prediction, calibration=None, context='plain_text'):
    heads=(calibration.get('head_acceptance',dict(tier=True,external=True)) if calibration else dict(tier=False,external=False))
    if calibration and 'context_acceptance' in calibration:
        supported=calibration['context_acceptance'].get(context,{})
        heads={head:heads[head] and supported.get(head,False) for head in heads}
    tier = temperature_probabilities([prediction['tier_scores'][t] for t in TIERS],
                                    calibration['tier_temperature'] if calibration and heads['tier'] else 1)
    external = float(binary_temperature(prediction['external_score'],
                                       calibration['external_temperature'] if calibration and heads['external'] else 1))
    ordered = sorted(map(float, tier), reverse=True)
    entropy = float(-(tier*np.log(np.maximum(tier, 1e-12))).sum()/np.log(len(TIERS)))
    reasons = []
    if prediction['vocabulary_coverage'] < .15:
        reasons.append('low_vocabulary_coverage')
    if ordered[0] < .6:
        reasons.append('low_tier_probability')
    if ordered[0]-ordered[1] < .15:
        reasons.append('close_tier_alternatives')
    if entropy > .7:
        reasons.append('high_tier_entropy')
    if prediction['tier'] == 'review':
        reasons.append('model_requests_review')
    context_evidence=(calibration.get('context_metrics',{}).get(context) if calibration else None)
    if context_evidence and context_evidence['tier']['after']['accuracy']<.8:
        reasons.append('limited_context_validation_accuracy')
    status=('synthetic_policy_calibrated' if all(heads.values()) else 'partially_synthetic_policy_calibrated') if any(heads.values()) else 'uncalibrated'
    return dict(status=status,
                calibration_context=context,
                scope='Agreement with authored synthetic policy labels; not probability of task success or best commercial model.',
                tier=dict(status='synthetic_policy_calibrated' if heads['tier'] else 'uncalibrated',distribution=dict(zip(TIERS, map(float, tier))),
                          top_probability=ordered[0], margin=ordered[0]-ordered[1], normalized_entropy=entropy),
                external_search=dict(status='synthetic_policy_calibrated' if heads['external'] else 'uncalibrated',yes=external, no=1-external),
                skills=dict(status='uncalibrated_selection_scores', mutually_exclusive=False,
                            note='Skill scores, including rescaled extension outputs, are not calibrated probabilities.'),
                vocabulary_coverage=prediction['vocabulary_coverage'], review_recommended=bool(reasons),
                review_reasons=reasons, affects_routing=False,
                evidence=(dict(check_cases=calibration['check_cases'],
                               tier_accuracy=calibration['metrics']['check']['tier']['after']['accuracy'],
                               tier_ece=calibration['metrics']['check']['tier']['after']['ece'],
                               external_accuracy=calibration['metrics']['check']['external']['after']['accuracy'])
                          if calibration else None),context_evidence=context_evidence)


def metrics(probabilities, labels):
    p = np.clip(np.asarray(probabilities, dtype=np.float64), 1e-12, 1)
    y = np.asarray(labels, dtype=int)
    truth = np.eye(p.shape[1])[y]
    confidence, chosen = p.max(axis=1), p.argmax(axis=1)
    correct = chosen == y
    ece = 0.
    for index in range(10):
        mask = (confidence >= index/10) & (confidence < (index+1)/10 if index < 9 else confidence <= 1)
        if mask.any():
            ece += float(mask.mean()*abs(confidence[mask].mean()-correct[mask].mean()))
    return dict(nll=float(-np.log(p[np.arange(len(y)), y]).mean()),
                brier=float(((p-truth)**2).sum(axis=1).mean()),
                ece=ece, accuracy=float(correct.mean()), cases=len(y))


def fit_calibration(model, rows, excluded_prompts=(), headwise=False):
    normalize = lambda text: ' '.join(text.lower().split())
    seen = set(map(normalize, excluded_prompts))
    for row in rows:
        prompt = row.get('prompt', '')
        if re.search(r'def assessment_(?:calibration|check)_(?:fast|balanced|deep|review)_',prompt):
            raise ValueError('Synthetic function names expose calibration labels')
        normalized = normalize(prompt)
        if not normalized or normalized in seen:
            raise ValueError('Empty, duplicate or previously used calibration prompt')
        seen.add(normalized)
        if row.get('split') not in ('calibration', 'check') or row.get('tier') not in TIERS or type(row.get('external')) is not bool:
            raise ValueError('Invalid probability labels or split')
    partitions = {split:[r for r in rows if r['split'] == split] for split in ('calibration', 'check')}
    for split, group in partitions.items():
        if any(sum(r['tier'] == tier for r in group) < 4 for tier in TIERS):
            raise ValueError('Each split needs at least four examples per tier')
        if min(sum(r['external'] for r in group), sum(not r['external'] for r in group)) < 4:
            raise ValueError('Each split needs four positive and four negative external labels')
    data = {}
    for split, group in partitions.items():
        tier, _, external = model.predict([r['prompt'] for r in group])
        data[split] = (tier, external, np.array([TIERS.index(r['tier']) for r in group]),
                       np.array([int(r['external']) for r in group]))
    tier, external, yt, yd = data['calibration']
    trials = np.geomspace(.1, 30, 160)
    tt = float(min(trials, key=lambda t: metrics(temperature_probabilities(tier, t), yt)['nll']))
    dt = float(min(trials, key=lambda t: metrics(np.column_stack((1-binary_temperature(external,t), binary_temperature(external,t))), yd)['nll']))
    reports = {}
    for split, (tier, external, yt, yd) in data.items():
        adjusted_tier = temperature_probabilities(tier, tt)
        adjusted_external = binary_temperature(external, dt)
        reports[split] = dict(tier=dict(before=metrics(tier,yt), after=metrics(adjusted_tier,yt)),
            external=dict(before=metrics(np.column_stack((1-external,external)),yd),
                          after=metrics(np.column_stack((1-adjusted_external,adjusted_external)),yd)))
    # Check set is never used to choose temperatures. Refuse calibration if it regresses.
    heads={head:all(reports['check'][head]['after'][metric] <= reports['check'][head]['before'][metric]+1e-6
                   for metric in ('nll','brier')) for head in ('tier','external')}
    accepted=all(heads.values())
    extra={}
    if headwise:
        import copy
        from tavi_model import is_coding_spec
        contexts={split:np.array(['python_spec' if is_coding_spec(r['prompt']) else 'plain_text' for r in group]) for split,group in partitions.items()}
        context_reports={};context_acceptance={}
        for context in sorted(set(contexts['check'])):
            mask=contexts['check']==context
            tier,external,yt,yd=data['check']
            pt=temperature_probabilities(tier,tt);pd=binary_temperature(external,dt)
            checks=dict(tier=dict(before=metrics(tier[mask],yt[mask]),after=metrics(pt[mask],yt[mask])),
                        external=dict(before=metrics(np.column_stack((1-external[mask],external[mask])),yd[mask]),
                                      after=metrics(np.column_stack((1-pd[mask],pd[mask])),yd[mask])))
            support=dict(tier=all(int((yt[mask]==i).sum())>=4 for i in range(4)),
                         external=min(int(yd[mask].sum()),int((1-yd[mask]).sum()))>=4)
            context_reports[context]=checks
            context_acceptance[context]={head:support[head] and all(checks[head]['after'][metric]<=checks[head]['before'][metric]+1e-6 for metric in ('nll','brier')) for head in heads}
        heads={head:any(v[head] for v in context_acceptance.values()) for head in heads}
        extra=dict(head_acceptance=heads,context_acceptance=context_acceptance,context_metrics=context_reports,
                   attempted_metrics=copy.deepcopy(reports),candidate_temperatures=dict(tier=tt,external=dt))
        for split,(tier,external,yt,yd) in data.items():
            use_tier=np.array([context_acceptance.get(context,{}).get('tier',False) for context in contexts[split]])
            use_external=np.array([context_acceptance.get(context,{}).get('external',False) for context in contexts[split]])
            pt=np.where(use_tier[:,None],temperature_probabilities(tier,tt),tier)
            pd=np.where(use_external,binary_temperature(external,dt),external)
            reports[split]['tier']['after']=metrics(pt,yt)
            reports[split]['external']['after']=metrics(np.column_stack((1-pd,pd)),yd)
        for head in heads:
            if not heads[head]:
                if head=='tier':tt=1.
                else:dt=1.
        accepted=any(heads.values())
    return dict(format='tavi-probability-v1', model_signature=signature(model.metadata),
                accepted=accepted, tier_temperature=tt, external_temperature=dt,
                fit_cases=len(partitions['calibration']), check_cases=len(partitions['check']),
                dataset_sha256=hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest(),
                scope='Authored synthetic policy calibration; small same-author check set, not real outcomes.',
                metrics=reports,**extra)
