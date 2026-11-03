"""Opt-in, local, pseudonymised computer-use evidence; no capture or actions.

Only sanitized numeric/enum fields are ever written. This is HOST-ATTESTED,
NOT independently audited evidence. A 32-byte secret HMACs the caller's site
family and stable task/trial key, allowing matched baseline/optimized analyses
without writing raw origins, tasks, labels, screenshots, or DOM observations.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime,timezone
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import statistics
import uuid

from tavi_metrics import ROUTES

FORMAT='tavi-consented-task-evidence-v1'
VARIANTS=frozenset({'baseline','optimized'})
OUTCOMES=frozenset({'success','failure','unverified'})
VISUAL_LABELS=frozenset({'visual_needed','visual_not_needed','uncertain'})
ROLES=frozenset({'button','link','tab','checkbox','switch','radio','menuitem','textbox','combobox'})
REASONS=frozenset({'unique_exact_control','no_exact_control','control_unavailable',
                   'ambiguous_control','stale_snapshot','future_snapshot'})
FIELDS=frozenset({'format','id','recorded_at','group_hmac','case_hmac','variant',
                  'route','role','reason','age_bucket','context_present',
                  'geometry_bucket','outcome','host_result_verified',
                  'visual_label','visual_label_verified','duration_ms',
                  'provider_input_tokens','provider_output_tokens',
                  'provider_cached_input_tokens','token_provenance',
                  'data_source','qualification_changed','automatic_action_authorized'})


def _number(value,name):
    if type(value) not in (int,float) or not math.isfinite(value) or value<0:
        raise ValueError('Invalid '+name)
    return round(float(value),4)


def _token(value,name):
    if value is not None and (type(value) is not int or value<0):
        raise ValueError('Invalid '+name)
    return value


def _secret(secret):
    if not isinstance(secret,bytes) or len(secret)<32:
        raise ValueError('A private HMAC secret of at least 32 bytes is required')
    return secret


def _digest(secret,label,text):
    if not isinstance(text,str) or not text.strip() or len(text)>512:
        raise ValueError('Invalid '+label)
    return hmac.new(_secret(secret),(label+'\0'+text).encode(),hashlib.sha256).hexdigest()


def _hex(value):
    if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('Invalid pseudonymised identifier')
    return value


def _age_bucket(age):
    if type(age) not in (float,int) or not math.isfinite(age):
        raise ValueError('Invalid host observation age')
    if age<0:return 'future'
    if age<=0.5:return '0-500ms'
    if age<=2:return '500-2000ms'
    if age<=5:return '2000-5000ms'
    return 'stale'


def _geometry_bucket(candidate):
    if candidate is None:return 'none'
    if not isinstance(candidate,dict):raise ValueError('Invalid candidate')
    bounds=candidate.get('bounds')
    if not isinstance(bounds,list) or len(bounds)!=4:
        raise ValueError('Invalid candidate bounds')
    x,y,w,h=bounds
    for value in (x,y,w,h):
        if type(value) not in (int,float) or not math.isfinite(value):
            raise ValueError('Invalid geometry')
    # Only coarse physical size, no position, label or coordinate persisted.
    area=max(0,w)*max(0,h)
    return 'small' if area<2000 else 'medium' if area<12000 else 'large'


def _tokens(input_tokens,output_tokens,cached_tokens,provenance):
    _token(input_tokens,'input tokens')
    _token(output_tokens,'output tokens')
    _token(cached_tokens,'cached tokens')
    if input_tokens is None or output_tokens is None:
        if input_tokens is not None or output_tokens is not None or cached_tokens is not None or provenance is not None:
            raise ValueError('Incomplete provider-reported token usage')
        return None,None,None,None
    if provenance!='provider_reported':
        raise ValueError('Only actual provider-reported token counts may be stored')
    if cached_tokens is not None and cached_tokens>input_tokens:
        raise ValueError('Cached tokens exceed input tokens')
    return input_tokens,output_tokens,cached_tokens,provenance


def validate(event):
    if not isinstance(event,dict) or set(event)!=FIELDS or event.get('format')!=FORMAT:
        raise ValueError('Invalid evidence schema')
    try:uuid.UUID(event['id'])
    except (ValueError,TypeError,AttributeError) as error:raise ValueError('Invalid event ID') from error
    date=datetime.fromisoformat(event['recorded_at'])
    if date.tzinfo is None:raise ValueError('Evidence timestamp must be timezone-aware')
    _hex(event['group_hmac']);_hex(event['case_hmac'])
    if event['variant'] not in VARIANTS or event['route'] not in ROUTES or event['role'] not in ROLES or event['reason'] not in REASONS:
        raise ValueError('Invalid categorical evidence')
    if event['age_bucket'] not in ('future','0-500ms','500-2000ms','2000-5000ms','stale'):
        raise ValueError('Invalid host age bucket')
    if event['geometry_bucket'] not in ('none','small','medium','large'):
        raise ValueError('Invalid geometry bucket')
    if type(event['context_present']) is not bool:
        raise ValueError('Invalid context flag')
    if event['outcome'] not in OUTCOMES or type(event['host_result_verified']) is not bool:
        raise ValueError('Invalid host outcome')
    if event['outcome']!='unverified' and not event['host_result_verified']:
        raise ValueError('Verified outcome required for success/failure label')
    label=event['visual_label']
    if label is not None and label not in VISUAL_LABELS:
        raise ValueError('Invalid visual label')
    if type(event['visual_label_verified']) is not bool or (label is not None and not event['visual_label_verified']):
        raise ValueError('Visual labels require explicit operator verification')
    if label is None and event['visual_label_verified']:
        raise ValueError('Visual label verification requires a label')
    _number(event['duration_ms'],'duration')
    _tokens(event['provider_input_tokens'],event['provider_output_tokens'],
            event['provider_cached_input_tokens'],event['token_provenance'])
    if event['data_source']!='consented_host_attested' or event['qualification_changed'] is not False or event['automatic_action_authorized'] is not False:
        raise ValueError('Evidence cannot authorize actions or change qualification')
    return event


def record(directory,packet,*,query_index=0,consent=False,
           sensitivity_reviewed=False,sensitive=True,secret=None,site_family=None,
           case_key=None,variant=None,outcome='unverified',host_result_verified=False,
           duration_ms=None,visual_label=None,visual_label_verified=False,
           input_tokens=None,output_tokens=None,cached_input_tokens=None,
           token_provenance=None):
    """Write only sanitized evidence after the operator's explicit opt-in.

    The *host* must supply a true task-family key and observed task outcome;
    Tavi neither browses, executes the action nor validates a site's consent.
    """
    if consent is not True or sensitivity_reviewed is not True or sensitive is not False:
        raise PermissionError('Explicit consent and non-sensitive page review are required')
    if not isinstance(packet,dict) or packet.get('format')!='tavi-observe-route-v1' or packet.get('authorization_granted') is not False or packet.get('executed_actions') is not False:
        raise ValueError('Expected non-executing Tavi observation packet')
    routes=packet.get('routes')
    if not isinstance(routes,list) or type(query_index) is not int or not 0<=query_index<len(routes):
        raise ValueError('Invalid query index')
    route=routes[query_index]
    if not isinstance(route,dict) or route.get('route') not in ROUTES:
        raise ValueError('Invalid route observation')
    control=route.get('control')
    if not isinstance(control,dict) or control.get('reason') not in REASONS or control.get('role') not in ROLES or control.get('age_seconds') is None:
        raise ValueError('Invalid source control')
    if route['route']=='host_control' and control['reason']!='unique_exact_control':
        raise ValueError('Contradictory host identity')
    if visual_label is not None and visual_label not in VISUAL_LABELS:
        raise ValueError('Invalid operator visual label')
    if visual_label is not None and visual_label_verified is not True:
        raise ValueError('Unverified visual label')
    if type(host_result_verified) is not bool or outcome not in OUTCOMES or (outcome!='unverified' and not host_result_verified):
        raise ValueError('Outcome requires host verification')
    if duration_ms is None:
        raise ValueError('Host-measured full task latency is required')
    token_values=_tokens(input_tokens,output_tokens,cached_input_tokens,token_provenance)
    event={
        'format':FORMAT,'id':str(uuid.uuid4()),
        'recorded_at':datetime.now(timezone.utc).isoformat(),
        'group_hmac':_digest(secret,'family',site_family),
        'case_hmac':_digest(secret,'case',case_key),
        'variant':variant,'route':route['route'],
        'role':control['role'],'reason':control['reason'],
        'age_bucket':_age_bucket(control['age_seconds']),
        'context_present':bool(control.get('context')),
        'geometry_bucket':_geometry_bucket(control.get('candidate')),
        'outcome':outcome,'host_result_verified':host_result_verified,
        'visual_label':visual_label,'visual_label_verified':visual_label_verified is True,
        'duration_ms':_number(duration_ms,'duration'),
        'provider_input_tokens':token_values[0],
        'provider_output_tokens':token_values[1],
        'provider_cached_input_tokens':token_values[2],
        'token_provenance':token_values[3],
        'data_source':'consented_host_attested',
        'qualification_changed':False,
        'automatic_action_authorized':False,
    }
    validate(event)
    directory=Path(directory)
    if directory.is_symlink():raise ValueError('Refuse symlinked evidence directory')
    directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    path=directory/(event['id']+'.json')
    # Exclusive file creation and mode600: local evidence must not be
    # replaced by another trial or silently made world-readable on POSIX.
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL
    flags |= getattr(os,'O_NOFOLLOW',0)
    fd=os.open(path,flags,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as stream:
        json.dump(event,stream,sort_keys=True,separators=(',',':'))
        stream.write('\n')
    return event


def load(directory):
    directory=Path(directory)
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError('Evidence directory missing or linked')
    paths=sorted(directory.glob('*.json'))
    if len(paths)>10000:raise ValueError('Too many evidence records')
    if sum(p.stat().st_size for p in paths)>32*1024*1024:
        raise ValueError('Evidence dataset exceeds 32MB')
    seen=set();events=[]
    for path in paths:
        if path.is_symlink() or path.stat().st_size>16384:
            raise ValueError('Unsafe evidence file')
        with path.open('rb') as stream:
            data=json.loads(stream.read().decode('utf-8-sig'))
        event=validate(data)
        if event['id'] in seen:raise ValueError('Duplicate evidence event ID')
        seen.add(event['id']);events.append(event)
    return events


def _percentile(samples,p):
    if not samples:return None
    samples=sorted(samples)
    return round(samples[max(0,math.ceil(len(samples)*p)-1)],2)


def _wilson(success,n):
    if not n:return None
    z=1.96;p=success/n;d=1+z*z/n
    center=(p+z*z/(2*n))/d
    span=z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/d
    return [round(max(0,center-span),4),round(min(1,center+span),4)]


def compare(events):
    """Matched, host-attested baseline/optimised observations only."""
    if not isinstance(events,list):
        raise ValueError('Expected validated evidence records')
    by_case={}
    for event in events:
        validate(event)
        pair=(event['group_hmac'],event['case_hmac'])
        slot=by_case.setdefault(pair,{})
        if event['variant'] in slot:
            raise ValueError('Duplicate variant per case; use a unique trial key for repetitions')
        slot[event['variant']]=event
    matched=[(v['baseline'],v['optimized']) for v in by_case.values() if set(v)==VARIANTS]
    verified=[(b,o) for b,o in matched if b['host_result_verified'] and o['host_result_verified']
              and b['outcome']!='unverified' and o['outcome']!='unverified']
    def variant_summary(index):
        samples=[pair[index] for pair in verified]
        durations=[v['duration_ms'] for v in samples]
        successes=sum(v['outcome']=='success' for v in samples)
        token_values=[v for v in samples if v['token_provenance']=='provider_reported']
        return dict(verified_tasks=len(samples),successes=successes,
            success_rate=round(successes/len(samples),4) if samples else None,
            wilson_95=_wilson(successes,len(samples)),
            median_ms=round(statistics.median(durations),2) if durations else None,
            p95_ms=_percentile(durations,.95),
            token_measured_tasks=len(token_values),
            input_tokens_total=sum(v['provider_input_tokens'] for v in token_values) if token_values else None,
            output_tokens_total=sum(v['provider_output_tokens'] for v in token_values) if token_values else None)
    token_pairs=[(b,o) for b,o in verified if b['token_provenance']=='provider_reported'
                 and o['token_provenance']=='provider_reported']
    return dict(format='tavi-matched-task-evaluation-v1',
        evidence='consented_host_attested_not_independently_audited',
        total_events=len(events),unique_case_keys=len(by_case),matched_pairs=len(matched),
        matched_verified_pairs=len(verified),paired_token_measured=len(token_pairs),
        baseline=variant_summary(0),optimized=variant_summary(1),
        paired_input_token_delta=(sum(o['provider_input_tokens']-b['provider_input_tokens']
                                      for b,o in token_pairs) if token_pairs else None),
        paired_output_token_delta=(sum(o['provider_output_tokens']-b['provider_output_tokens']
                                       for b,o in token_pairs) if token_pairs else None),
        real_task_success_claimed=False,automatic_action_qualified=False,
        cautions=['Only consented host attestations, not independent outcome verification.',
                  'Matched comparisons exclude unverified outcomes and require the same HMAC trial key.',
                  'Token deltas require both variants to report real provider usage.',
                  'This report never enables computer input or learns a policy.'])


def main(argv=None):
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path,help='Consented JSON evidence directory')
    args=parser.parse_args(argv)
    print(json.dumps(compare(load(args.directory)),indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
