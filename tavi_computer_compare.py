"""Consented, pseudonymised full-task Computer vs Computer+Tavi comparisons.

Host-supplied records only. No task capture, Computer invocation, clicks,
screenshots, API usage, or independent result verification are claimed.
No URLs, tasks, page titles, controls or model names are stored.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
from statistics import median
from uuid import uuid4

FORMAT = 'tavi-computer-matched-task-v1'
MODES = frozenset({'computer_only','computer_tavi'})
FIELDS = frozenset({
    'format','case_hmac','family_hmac','mode','environment_hmac',
    'planner_hmac','outcome','host_verified','elapsed_ms','screenshots',
    'provider_input_tokens','provider_output_tokens','provider_usage',
    'source','consent_confirmed','automatic_action_authorized',
})


def _digest(secret, scope, content):
    if not isinstance(secret, bytes) or len(secret) < 32:
        raise ValueError('A private 32+ byte HMAC key is mandatory')
    if not isinstance(content, str) or not content.strip() or len(content) > 512:
        raise ValueError('Invalid host grouping key')
    return hmac.new(secret,(scope+'\0'+content).encode('utf-8'),
                    hashlib.sha256).hexdigest()


def _hex(value):
    if (not isinstance(value,str) or len(value)!=64
            or any(char not in '0123456789abcdef' for char in value)):
        raise ValueError('Invalid pseudonymized key')


def validate(record):
    if (not isinstance(record,dict) or set(record)!=FIELDS
            or record.get('format') != FORMAT):
        raise ValueError('Unexpected matched Computer telemetry fields')
    for key in ('case_hmac','family_hmac','environment_hmac','planner_hmac'):
        _hex(record[key])
    if record['mode'] not in MODES:
        raise ValueError('Unknown Computer comparison mode')
    if (record['source'] != 'consented_host_attested'
            or record['consent_confirmed'] is not True
            or record['automatic_action_authorized'] is not False):
        raise ValueError('No consent or unsupported authority')
    if record['outcome'] not in ('success','failure','unverified'):
        raise ValueError('Invalid task outcome')
    if type(record['host_verified']) is not bool:
        raise ValueError('Invalid host verification')
    if record['outcome']!='unverified' and not record['host_verified']:
        raise ValueError('Outcome is not host-verified')
    elapsed=record['elapsed_ms']
    if type(elapsed) not in (int,float) or not math.isfinite(elapsed) or elapsed<0:
        raise ValueError('Invalid full-task wall time')
    count=record['screenshots']
    if type(count) is not int or count<0 or count>100_000:
        raise ValueError('Invalid screenshots count')
    inp,out=record['provider_input_tokens'],record['provider_output_tokens']
    if record['provider_usage'] == 'provider_reported':
        if (type(inp) is not int or inp<0 or
                type(out) is not int or out<0):
            raise ValueError('Provider usage requires actual token integers')
    elif record['provider_usage'] == 'unavailable':
        if inp is not None or out is not None:
            raise ValueError('Cannot infer tokens without provider usage')
    else:
        raise ValueError('Unsupported token provenance')
    return record


def attest(*, secret, case_key, family, mode, environment, planner,
           outcome, host_verified, elapsed_ms, screenshots,
           input_tokens=None, output_tokens=None, provider_usage='unavailable',
           consent=False, sensitivity_reviewed=False, sensitive=True):
    """Accept only explicitly consented, non-sensitive HOST MEASUREMENTS."""
    if consent is not True or sensitivity_reviewed is not True or sensitive is not False:
        raise PermissionError('Require specific non-sensitive host task consent and review')
    record=dict(
        format=FORMAT, case_hmac=_digest(secret,'case',case_key),
        family_hmac=_digest(secret,'family',family),
        mode=mode,environment_hmac=_digest(secret,'environment',environment),
        planner_hmac=_digest(secret,'planner',planner),
        outcome=outcome,host_verified=host_verified,
        elapsed_ms=elapsed_ms,screenshots=screenshots,
        provider_input_tokens=input_tokens,
        provider_output_tokens=output_tokens,provider_usage=provider_usage,
        source='consented_host_attested',consent_confirmed=True,
        automatic_action_authorized=False)
    return validate(record)


def save(directory, record):
    validate(record)
    directory=Path(directory)
    if directory.is_symlink():
        raise ValueError('Refuse symlinked evidence directory')
    directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    path=directory/(uuid4().hex+'.json')
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0)
    handle=os.open(path,flags,0o600)
    with os.fdopen(handle,'w',encoding='utf-8') as stream:
        json.dump(record,stream,sort_keys=True,separators=(',',':'))
        stream.write('\n')
    return path


def read(directory):
    directory=Path(directory)
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError('Missing or unsafe evidence directory')
    paths=list(directory.glob('*.json'))
    if len(paths)>10_000:raise ValueError('Too many evidence records')
    results=[]
    for path in paths:
        if path.is_symlink() or path.stat().st_size>16_384:
            raise ValueError('Unsafe evidence file')
        with path.open('r',encoding='utf-8') as source:
            results.append(validate(json.load(source)))
    return results


def _p95(samples):
    if not samples:return None
    samples=sorted(samples)
    return round(samples[math.ceil(.95*len(samples))-1],3)


def compare(records):
    # All pairings are made with HMAC pseudonyms; do not use raw task IDs.
    by_case={}
    for item in records:
        validate(item)
        key=(item['case_hmac'],item['family_hmac'])
        modes=by_case.setdefault(key,{})
        if item['mode'] in modes:
            raise ValueError('Duplicate mode; use a distinct case key for repeats')
        modes[item['mode']]=item
    all_pairs=[(pair['computer_only'],pair['computer_tavi'])
               for pair in by_case.values() if set(pair)==MODES]
    same_env=[(a,b) for a,b in all_pairs
              if a['environment_hmac']==b['environment_hmac']
              and a['planner_hmac']==b['planner_hmac']]
    verified=[(a,b) for a,b in same_env
              if a['host_verified'] and b['host_verified']
              and a['outcome']!='unverified' and b['outcome']!='unverified']
    tokens=[(a,b) for a,b in verified if a['provider_usage']=='provider_reported'
            and b['provider_usage']=='provider_reported']
    def per_mode(index):
        samples=[item[index] for item in verified]
        times=[item['elapsed_ms'] for item in samples]
        return dict(
            verified_tasks=len(samples),
            successes=sum(item['outcome']=='success' for item in samples),
            median_task_ms=round(median(times),3) if times else None,
            p95_task_ms=_p95(times),
            total_screenshots=sum(item['screenshots'] for item in samples)
              if samples else None)
    deltas=[a['elapsed_ms']-b['elapsed_ms'] for a,b in verified]
    ratios=[a['elapsed_ms']/b['elapsed_ms'] for a,b in verified if b['elapsed_ms']>0]
    return dict(
        format='tavi-computer-host-matched-comparison-v1',
        evidence='consented_host_attested_not_independent',
        records=len(records),unpaired_or_incomplete=len(by_case)-len(all_pairs),
        matched_pairs=len(all_pairs),
        rejected_different_planner_or_environment=len(all_pairs)-len(same_env),
        host_verified_pairs=len(verified),provider_token_pairs=len(tokens),
        computer_only=per_mode(0),computer_tavi=per_mode(1),
        median_paired_ms_saved=round(median(deltas),3) if deltas else None,
        median_paired_speed_ratio=round(median(ratios),3) if ratios else None,
        paired_input_tokens_saved=(sum(a['provider_input_tokens']-b['provider_input_tokens']
                                       for a,b in tokens) if tokens else None),
        paired_output_tokens_saved=(sum(a['provider_output_tokens']-b['provider_output_tokens']
                                        for a,b in tokens) if tokens else None),
        independently_verified=False,
        claims_full_computer_task_improvement=False,
        note='No Computer/AI task execution occurs in this tool; estimates are unavailable without complete consented host records.')


def main(argv=None):
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    args=parser.parse_args(argv)
    print(json.dumps(compare(read(args.directory)),indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
