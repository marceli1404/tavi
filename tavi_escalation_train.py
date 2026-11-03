"""Offline, group-held-out *advisory* visual-review model training.

Never learns a click or skips mandatory evidence. Output may only REQUEST
additional visual review for already exact host controls. It is not plugged
into production routing and cannot change the failed auto-action gate.
No real training is claimed without consented labelled observations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path

import numpy as np
from tavi_field_data import load,validate

FORMAT='tavi-additional-visual-review-candidate-v1'
MIN_CASES=80
MIN_FAMILIES=8
ROLES=('button','link','tab','menuitem','checkbox','switch','radio','textbox','combobox')
FEATURES=(
    'context_present','geometry_small','geometry_medium','geometry_large',
    'age_0-500ms','age_500-2000ms','age_2000-5000ms',
) + tuple('role_'+r for r in ROLES)


def feature_vector(event):
    validate(event)
    if event['route']!='host_control' or event['reason']!='unique_exact_control':
        raise ValueError('Optional visual review is only evaluated for unique exact host controls')
    return np.array([
        float(event['context_present']),
        float(event['geometry_bucket']=='small'),
        float(event['geometry_bucket']=='medium'),
        float(event['geometry_bucket']=='large'),
        float(event['age_bucket']=='0-500ms'),
        float(event['age_bucket']=='500-2000ms'),
        float(event['age_bucket']=='2000-5000ms'),
        *(float(event['role']==role) for role in ROLES),
    ],dtype=np.float64)


def _sigmoid(x):
    return 1/(1+np.exp(-np.clip(x,-30,30)))


def _eligible(events):
    cases={}
    for event in events:
        validate(event)
        if (event['route']!='host_control' or event['reason']!='unique_exact_control'
            or not event['visual_label_verified']
            or event['visual_label'] not in ('visual_needed','visual_not_needed')):
            continue
        key=(event['group_hmac'],event['case_hmac'])
        old=cases.get(key)
        if old:
            if old['visual_label']!=event['visual_label'] or feature_vector(old).tolist()!=feature_vector(event).tolist():
                raise ValueError('Conflicting labels/features for a paired task')
            continue
        cases[key]=event
    return list(cases.values())


def train(events):
    selected=_eligible(events)
    families=sorted({e['group_hmac'] for e in selected},
                    key=lambda group:hashlib.sha256(('holdout-v1:'+group).encode()).hexdigest())
    if len(selected)<MIN_CASES or len(families)<MIN_FAMILIES:
        raise ValueError('Insufficient distinct consented labelled cases or task families')
    # Group holdout prevents leaking site/task-family-specific repeated UI
    # traces from training into evaluation.
    holdout=set(families[:max(2,round(len(families)*.25))])
    testing=[e for e in selected if e['group_hmac'] in holdout]
    training=[e for e in selected if e['group_hmac'] not in holdout]
    if min(len(testing),len(training))<20:
        raise ValueError('Insufficient cases per independent family split')
    y_train=np.array([int(e['visual_label']=='visual_needed') for e in training],dtype=np.float64)
    y_test=np.array([int(e['visual_label']=='visual_needed') for e in testing],dtype=np.float64)
    if len(set(y_train))!=2 or len(set(y_test))!=2:
        raise ValueError('Both classes required in independent training and holdout groups')
    X=np.stack([feature_vector(e) for e in training])
    H=np.stack([feature_vector(e) for e in testing])
    weights=np.zeros(len(FEATURES),dtype=np.float64)
    bias=0.0
    # Conservative deterministic L2 logistic baseline, not a frontier
    # neural agent or reinforcement-learned computer-use policy.
    for _ in range(600):
        errors=_sigmoid(X@weights+bias)-y_train
        weights-=.35*(X.T@errors/len(X)+.02*weights)
        bias-=.35*float(errors.mean())
    predictions=_sigmoid(H@weights+bias)
    brier=float(np.mean((predictions-y_test)**2))
    constant=float(np.mean(y_train))
    baseline_brier=float(np.mean((constant-y_test)**2))
    labels=predictions>=.5
    fn=int(np.sum((~labels)&(y_test==1)))
    fp=int(np.sum(labels&(y_test==0)))
    tp=int(np.sum(labels&(y_test==1)))
    tn=int(np.sum((~labels)&(y_test==0)))
    report=dict(
        format=FORMAT,policy='request_more_evidence_only_not_an_action_model',
        features=list(FEATURES),weights=[round(float(x),10) for x in weights],
        bias=round(bias,10),decision_threshold=.5,
        training_cases=len(training),holdout_cases=len(testing),
        training_families=len(families)-len(holdout),holdout_families=len(holdout),
        training_positive=int(sum(y_train)),holdout_positive=int(sum(y_test)),
        heldout_brier=round(brier,6),
        heldout_constant_baseline_brier=round(baseline_brier,6),
        heldout_confusion=dict(tp=tp,fp=fp,tn=tn,fn=fn),
        heldout_accuracy=round((tp+tn)/len(y_test),4),
        heldout_false_negative_rate=round(fn/(fn+tp),4) if fn+tp else None,
        independent_ground_truth=False,
        source='operator_verified_host_attested',
        model_adopted=False,
        production_routing_changed=False,
        may_skip_ocr=False,may_click=False,
        automatic_probability_qualified=False,
        limitations='Heldout site-family validation of self/host-attested visual-review labels only; no real browser success or action safety established.')
    return report


def score(model,event):
    if not isinstance(model,dict) or model.get('format')!=FORMAT or model.get('may_click') is not False or model.get('may_skip_ocr') is not False or model.get('model_adopted') is not False:
        raise ValueError('Only non-deployed advisory visual-review model allowed')
    if model.get('features')!=list(FEATURES) or model.get('decision_threshold')!=.5:
        raise ValueError('Unknown advisory model features')
    weights=model.get('weights')
    if not isinstance(weights,list) or len(weights)!=len(FEATURES) or any(type(w) not in (float,int) or not math.isfinite(w) for w in weights):
        raise ValueError('Invalid advisory weights')
    bias=model.get('bias')
    if type(bias) not in (float,int) or not math.isfinite(bias):
        raise ValueError('Invalid advisory bias')
    value=float(_sigmoid(feature_vector(event)@np.array(weights,dtype=np.float64)+bias))
    return dict(format='tavi-optional-visual-review-suggestion-v1',
                advisory_score=round(value,6),
                suggest_additional_visual_check=value>=.5,
                action_authorized=False,may_skip_mandatory_evidence=False,
                automatic_probability_qualified=False)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    parser.add_argument('--candidate-output',type=Path,
                        help='Opt-in write a new unactivated candidate JSON; never overwrites')
    args=parser.parse_args(argv)
    report=train(load(args.directory))
    if args.candidate_output:
        path=args.candidate_output
        if path.is_symlink():raise ValueError('Refuse linked output')
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            json.dump(report,f,indent=2)
            f.write('\n')
    print(json.dumps({k:v for k,v in report.items() if k!='weights'},indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
