"""Verified, paired Computer-only vs Computer+Tavi task results.

This is a data *validator and analyzer*, not an autonomous Computer backend.
It intentionally does not fabricate real Windows sessions or API usage.
The trusted Computer host records numeric outcomes for real consented tasks.
No prompts, window titles, filenames, handles, screenshots, model responses,
paths, URLs or raw accessibility text belong in the input schema.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import median

MODES=('computer_only','computer_tavi')
NUMERIC=('duration_ms','screenshots','input_tokens','output_tokens')
REQUIRED={'task_id','variant','model_id','host_backend','environment_id',
          'consented','verified_success','duration_ms','screenshots',
          'input_tokens','output_tokens','provider_usage_source',
          'permission_incidents'}
ALLOWED=REQUIRED|{'cache_read_tokens','cache_write_tokens'}
MODEL_USAGE=('provider_reported','unavailable')


def _number(value,*,integer=False,positive=False):
    if type(value) not in (int,float) or (integer and type(value) is not int):
        return False
    import math
    return math.isfinite(value) and (value>0 if positive else value>=0)


def validate(records):
    if not isinstance(records,list) or not 2<=len(records)<=2000:
        raise ValueError('Expected 2–2000 numeric consented task records')
    pairs={}
    for r in records:
        if not isinstance(r,dict) or set(r)-ALLOWED or not REQUIRED<=set(r):
            raise ValueError('Unexpected or missing task metrics fields')
        if r['variant'] not in MODES or type(r['consented']) is not bool or r['consented'] is not True:
            raise ValueError('Unknown variant or missing explicit evidence consent')
        if type(r['verified_success']) is not bool:
            raise ValueError('Task outcome must be independently verified by Computer')
        if not isinstance(r['task_id'],str) or not (
                len(r['task_id'])==32 and all(x in '0123456789abcdef' for x in r['task_id'])):
            raise ValueError('Use a pseudonymous 32-character hexadecimal task ID')
        for key in ('model_id','host_backend','environment_id'):
            if not isinstance(r[key],str) or not r[key].strip() or len(r[key])>128:
                raise ValueError('Invalid environment or model identifier')
        if not _number(r['duration_ms'],positive=True):
            raise ValueError('Task must include verified full wall-clock duration')
        for key in ('screenshots','permission_incidents'):
            if r[key] is not None and not _number(r[key],integer=True):
                raise ValueError('Invalid numeric screenshot/incident count')
        source=r['provider_usage_source']
        if source not in MODEL_USAGE:
            raise ValueError('Invalid model usage provenance')
        for key in ('input_tokens','output_tokens','cache_read_tokens','cache_write_tokens'):
            val=r.get(key)
            if val is not None and not _number(val,integer=True):
                raise ValueError('Invalid provider token count')
            if source=='unavailable' and val is not None:
                raise ValueError('Unknown provider usage must be null')
        if source=='provider_reported' and (
                r['input_tokens'] is None or r['output_tokens'] is None):
            raise ValueError('Provider usage cannot be claimed without both token totals')
        key=r['task_id']
        pair=pairs.setdefault(key,{})
        if r['variant'] in pair:
            raise ValueError('Duplicate task/variant measurement')
        pair[r['variant']]=r
    for key,pair in pairs.items():
        if set(pair)!=set(MODES):
            raise ValueError('Each task must have both variants')
        a,b=(pair[mode] for mode in MODES)
        for key in ('model_id','host_backend','environment_id'):
            if a[key]!=b[key]:
                raise ValueError('Matched tasks must share planner model, executor and environment')
    return pairs


def summarize(records):
    pairs=validate(records)
    results={}
    for mode in MODES:
        subset=[pair[mode] for pair in pairs.values()]
        successful=sum(item['verified_success'] for item in subset)
        durations=[item['duration_ms'] for item in subset]
        results[mode]=dict(
            attempts=len(subset),verified_successes=successful,
            success_rate=round(successful/len(subset),4),
            median_full_task_ms=round(median(durations),3),
            permission_incidents=sum(item['permission_incidents'] for item in subset
                                     if item['permission_incidents'] is not None))
    valid=[(pair['computer_only'],pair['computer_tavi']) for pair in pairs.values()]
    both_success=[(a,b) for a,b in valid if a['verified_success'] and b['verified_success']]
    paired_deltas=[a['duration_ms']-b['duration_ms'] for a,b in valid]
    same_complete=[(a['duration_ms']/b['duration_ms']) for a,b in both_success]
    screenshots=[(a['screenshots'],b['screenshots']) for a,b in valid
                 if a['screenshots'] is not None and b['screenshots'] is not None]
    reported=[(a,b) for a,b in valid if
              a['provider_usage_source']==b['provider_usage_source']=='provider_reported']
    def totals(key):
        return {mode:sum(item[key] for item in pair) for mode,pair in (
            ('computer_only',[a for a,b in reported]),
            ('computer_tavi',[b for a,b in reported]))}
    results['matched']=dict(
        pairs=len(valid),both_succeeded=len(both_success),
        median_paired_wall_time_delta_ms=round(median(paired_deltas),3),
        median_successful_paired_speed_ratio=round(median(same_complete),3)
          if same_complete else None,
        screenshot_pairs_measured=len(screenshots),
        screenshot_totals={
            'computer_only':sum(a for a,b in screenshots),
            'computer_tavi':sum(b for a,b in screenshots)}
             if screenshots else None,
        provider_token_pairs_measured=len(reported),
        provider_token_totals={
            'input':totals('input_tokens'),
            'output':totals('output_tokens')
        } if reported else None,
        model_cost=None,
    )
    return dict(format='tavi-computer-matched-field-comparison-v1',
                scope='Consented host-verified paired full task outcomes; user must supply real evidence',
                input_contains_no_prompts_or_accessibility_text=True,
                trials=results,real_field_data_supplied=True,
                no_unreported_provider_usage_imputed=True)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True,
                        help='Existing approved numeric-only evidence file')
    parser.add_argument('--output',type=Path,required=True,
                        help='NEW report path; never overwrite')
    args=parser.parse_args(argv)
    with args.input.open('r',encoding='utf-8') as stream:
        dataset=json.load(stream)
    report=summarize(dataset)
    with args.output.open('x',encoding='utf-8') as stream:
        json.dump(report,stream,indent=2)
        stream.write('\n')
    print(json.dumps(report,indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
