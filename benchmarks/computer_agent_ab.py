"""Strict, host-recorded matched Computer vs Computer+Tavi field-task evaluator.

A trusted host submits one numeric-only JSONL record for each completed or
failed trial. No screenshots, URLs, window labels, user prompts, credentials
or task data are stored. This tool never launches Computer, clicks, observes
apps or calls a model. Empty or unmatched evidence is NOT a benchmark.

Every comparison requires the same environment, planner, executor and task
family. Tokens count only when BOTH variants contain provider-reported usage.
Provider cost only counts when BOTH variants contain invoice-backed amounts.
Outcomes are host-reported, not independently established by this tool.
"""
from __future__ import annotations

from collections import Counter
import argparse
import json
import math
from pathlib import Path
import re
from statistics import median

FORMAT = 'tavi-computer-matched-host-eval-v1'
MODES = ('computer', 'computer_tavi')
FAMILIES = frozenset(('file_explorer','settings','dialog','form','navigation','other'))
TASK_SOURCES = frozenset(('controlled_fixture','consented_real_task'))
IDENTIFIER = re.compile(r'^[A-Za-z0-9_-]{6,80}$')
REQUIRED = {
    'trial_id','pair_id','mode','task_family','task_source','planner_id',
    'executor_id','environment_id','success','outcome_verified',
    'duration_ms','screenshots','native_observations','actions_attempted',
    'unexpected_actions','provider_tokens','provider_cost_usd',
}
MAX_ROWS = 1000
MAX_BYTES = 4_000_000


def _object(pairs):
    output = {}
    for key, value in pairs:
        if key in output:
            raise ValueError('Duplicate JSON field')
        output[key] = value
    return output


def _nonnegative_int(value, key):
    if type(value) is not int or not 0 <= value <= 100000:
        raise ValueError('Invalid '+key)
    return value


def _money(value):
    if value is None:
        return None
    if (type(value) not in (int,float) or
            not math.isfinite(value) or not 0 <= value <= 100000):
        raise ValueError('Invalid provider-invoiced cost')
    return float(value)


def validate(record):
    if not isinstance(record,dict) or set(record)!=REQUIRED:
        raise ValueError('Missing or unexpected trial fields')
    for field in ('trial_id','pair_id','planner_id','executor_id','environment_id'):
        value = record[field]
        if not isinstance(value,str) or not IDENTIFIER.fullmatch(value):
            raise ValueError('Invalid anonymous trial identifier: '+field)
    if record['mode'] not in MODES or record['task_family'] not in FAMILIES:
        raise ValueError('Invalid mode or task family')
    if record['task_source'] not in TASK_SOURCES:
        raise ValueError('Invalid task source')
    if (record['success'] is not True and record['success'] is not False):
        raise ValueError('Explicit success is required, including failed trials')
    if record['outcome_verified'] is not True:
        raise ValueError('Trusted host must verify every result, including failures')
    elapsed = record['duration_ms']
    if (type(elapsed) not in (int,float) or not math.isfinite(elapsed)
            or not 0 < elapsed <= 7_200_000):
        raise ValueError('Invalid complete task duration')
    for field in ('screenshots','native_observations',
                  'actions_attempted','unexpected_actions'):
        _nonnegative_int(record[field],field)
    if record['unexpected_actions']>record['actions_attempted']:
        raise ValueError('Unexpected actions exceed attempts')
    tokens = record['provider_tokens']
    if tokens is not None:
        if (not isinstance(tokens,dict) or
                set(tokens) != {'input','output','source'} or
                tokens['source'] != 'provider_reported'):
            raise ValueError('Only provider-reported input/output usage is accepted')
        _nonnegative_int(tokens['input'],'input tokens')
        _nonnegative_int(tokens['output'],'output tokens')
    # A cost value represents billed/provider-invoiced cost entered by the
    # host; do not infer price from token count. The host must verify this.
    _money(record['provider_cost_usd'])
    return record


def load_jsonl(path):
    path = Path(path)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError('Host evaluation data exceeds 4 MB')
    rows=[]
    with path.open('r',encoding='utf-8') as handle:
        for line in handle:
            if not line.strip():
                continue
            if len(rows) >= MAX_ROWS:
                raise ValueError('Too many task trials')
            item = json.loads(line,object_pairs_hook=_object,
                              parse_constant=lambda x: (_ for _ in ()).throw(
                                  ValueError('Nonfinite JSON value')))
            rows.append(validate(item))
    if not rows:
        raise ValueError('No task evidence; run real authorised matched tasks')
    return rows


def _pair(rows):
    trials=set()
    by_id={}
    for row in rows:
        if row['trial_id'] in trials:
            raise ValueError('Duplicate trial ID')
        trials.add(row['trial_id'])
        pair=by_id.setdefault(row['pair_id'],{})
        if row['mode'] in pair:
            raise ValueError('Duplicate mode within a task pair')
        pair[row['mode']]=row
    pairs=[]
    for ident,variants in by_id.items():
        if set(variants)!=set(MODES):
            raise ValueError('Unmatched task pair: '+ident)
        a,b=variants['computer'],variants['computer_tavi']
        for key in ('planner_id','executor_id','environment_id',
                    'task_family','task_source'):
            if a[key]!=b[key]:
                raise ValueError('Task pair changes '+key+': '+ident)
        pairs.append((a,b))
    return pairs


def _pct(baseline,alternative):
    if baseline<=0:
        return None
    return round(100*(1-alternative/baseline),2)


def evaluate(rows):
    if not isinstance(rows,list) or not 2 <= len(rows) <= MAX_ROWS:
        raise ValueError('Expected matched task trial rows')
    for row in rows:
        validate(row)
    pairs=_pair(rows)
    total={}
    for mode in MODES:
        sample=[record for record in rows if record['mode']==mode]
        total[mode]={
            'trials':len(sample),
            'verified_successes':sum(x['success'] for x in sample),
            'success_rate':round(sum(x['success'] for x in sample)/len(sample),4),
            'median_complete_task_ms':round(median(x['duration_ms'] for x in sample),3),
            'screenshots_total':sum(x['screenshots'] for x in sample),
            'native_observations_total':sum(x['native_observations'] for x in sample),
            'actions_attempted_total':sum(x['actions_attempted'] for x in sample),
            'unexpected_actions_total':sum(x['unexpected_actions'] for x in sample),
        }
    duration_ratios=[a['duration_ms']/b['duration_ms'] for a,b in pairs]
    duration_deltas=[a['duration_ms']-b['duration_ms'] for a,b in pairs]
    token_pairs=[(a,b) for a,b in pairs
                 if a['provider_tokens'] is not None and b['provider_tokens'] is not None]
    token_usage=None
    if token_pairs:
        base=sum(a['provider_tokens']['input']+a['provider_tokens']['output']
                 for a,b in token_pairs)
        new=sum(b['provider_tokens']['input']+b['provider_tokens']['output']
                for a,b in token_pairs)
        token_usage=dict(pairs=len(token_pairs),baseline_tokens=base,
                         tavi_tokens=new,reduction_pct=_pct(base,new),
                         excludes_pairs_without_both_provider_reports=True)
    invoice_pairs=[(a,b) for a,b in pairs
                   if a['provider_cost_usd'] is not None
                   and b['provider_cost_usd'] is not None]
    invoice=None
    if invoice_pairs:
        base=sum(a['provider_cost_usd'] for a,b in invoice_pairs)
        new=sum(b['provider_cost_usd'] for a,b in invoice_pairs)
        invoice=dict(pairs=len(invoice_pairs),
                     baseline_usd=round(base,5),tavi_usd=round(new,5),
                     reduction_pct=_pct(base,new),
                     excludes_pairs_without_both_invoices=True)
    return {
        'format':FORMAT,
        'data_scope':dict(
            rows=len(rows),pairs=len(pairs),
            controlled_fixture_pairs=sum(a['task_source']=='controlled_fixture'
                                         for a,b in pairs),
            consented_real_task_pairs=sum(a['task_source']=='consented_real_task'
                                          for a,b in pairs),
            provenance='host_reported_not_independently_audited',
        ),
        'modes':total,
        'matched':{
            'median_paired_wall_time_ratio':round(median(duration_ratios),3),
            'median_paired_wall_time_saved_ms':round(median(duration_deltas),3),
            'both_succeeded':sum(a['success'] and b['success'] for a,b in pairs),
            'both_failed':sum(not a['success'] and not b['success'] for a,b in pairs),
            'baseline_only_succeeded':sum(a['success'] and not b['success']
                                           for a,b in pairs),
            'tavi_only_succeeded':sum(not a['success'] and b['success']
                                       for a,b in pairs),
            'screenshot_reduction_pct':_pct(
                total['computer']['screenshots_total'],
                total['computer_tavi']['screenshots_total']),
            'provider_tokens':token_usage,
            'provider_invoiced_cost':invoice,
            'no_unexpected_actions_observed':(
                sum(x['unexpected_actions'] for x in rows)==0),
        },
        'limits':{
            'does_not_execute_computer':True,
            'does_not_measure_missing_provider_tokens':True,
            'claims_task_outcomes_only_as_host_reported':True,
            'cannot_independently_verify_environment_or_permissions':True,
            'failure_trials_included':True,
        },
    }


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input_jsonl',type=Path,help='Anonymised host-reported matched trials')
    parser.add_argument('--output',type=Path,help='NEW summary file, never overwrite')
    args=parser.parse_args(argv)
    result=evaluate(load_jsonl(args.input_jsonl))
    if args.output:
        with args.output.open('x',encoding='utf-8') as output:
            json.dump(result,output,indent=2)
            output.write('\n')
    print(json.dumps(result,indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
