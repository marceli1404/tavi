"""Measure compact Tavi *planner input tokens* and projection CPU overhead.

Uses offline tokenizer encodings (cl100k_base, o200k_base), not API calls.
These are tokenizer-proxy counts for the specified JSON message bodies;
they are NOT provider-billed tokens or an end-to-end agent comparison.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import argparse
import json
import math
from pathlib import Path
from statistics import median
import time

from tavi_observe import dispatch
from tavi_observe_wire import planner_packet


LABELS = [
    'Open settings', 'Create workspace', 'Export report', 'Open insights',
    'View notifications', 'Create project', 'Manage access', 'Download summary',
    'Review changes', 'Add a filter', 'Inspect tasks', 'Open dashboard',
    'Apply changes', 'Show history', 'Save changes', 'Open navigation',
]


def fixture(*,controls_count=16,queries_count=16,variant='exact'):
    if (type(controls_count) is not int or not 0<=controls_count<=16
            or type(queries_count) is not int or not 1<=queries_count<=16
            or variant not in ('exact', 'mixed', 'unavailable', 'ambiguous','stale')):
        raise ValueError('Unsupported fixed workload')
    controls=[]
    for index in range(controls_count):
        controls.append(dict(
            id=f'control-{index}',label=LABELS[index],role='button',
            context='Test controls',visible=True,enabled=True,
            bounds=[30+(index%4)*200,40+(index//4)*98,160,52]))
    if variant == 'unavailable' and controls:
        controls[0]['enabled']=False
    if variant == 'ambiguous' and controls:
        controls.append(dict(controls[0],id='duplicate-control'))
    age=8 if variant=='stale' else 0
    snapshot=dict(
        format='tavi-control-snapshot-v1',source='supported_browser_dom',
        snapshot_id='benchmark-snapshot',
        captured_at=(datetime.now(timezone.utc)-timedelta(seconds=age)).isoformat(),
        viewport=[900,700],controls=controls)
    queries=[dict(id=f'q{i}',task='Inspect '+LABELS[i],
                  target=LABELS[i],role='button')
             for i in range(queries_count)]
    return snapshot,queries


CASES = {
    'one_exact': (1,1,'exact'),
    'four_exact': (4,4,'exact'),
    'sixteen_exact': (16,16,'exact'),
    'twelve_exact_four_missing': (12,16,'mixed'),
    'one_disabled': (4,4,'unavailable'),
    'one_ambiguous': (4,4,'ambiguous'),
    'stale_observation': (4,4,'stale'),
}


def wire(packet):
    return json.dumps(packet,ensure_ascii=False,allow_nan=False,
                      separators=(',', ':')).encode('utf-8')


def benchmark(*,iterations=60, encoders=None):
    if type(iterations) is not int or not 5<=iterations<=1000:
        raise ValueError('iterations must be an integer between 5 and 1000')
    if encoders is None:
        import tiktoken  # optional benchmark-only dependency; not Tavi runtime
        encoders={name:tiktoken.get_encoding(name) for name in (
            'cl100k_base','o200k_base')}
    if not isinstance(encoders,dict) or not encoders:
        raise ValueError('Expected at least one tokenizer')
    cases=[]
    for label,(controls,number,variant) in CASES.items():
        snapshot,queries=fixture(controls_count=controls,
                                 queries_count=number,variant=variant)
        full=dispatch(snapshot,queries)
        full.update(status='routed',request_id='bench')
        smaller=planner_packet(full)
        baseline=wire(full)
        compact=wire(smaller)
        timings=[]
        for _ in range(iterations):
            started=time.perf_counter()
            result=planner_packet(full)
            wire(result)
            timings.append((time.perf_counter()-started)*1000)
        token_results={}
        for name,encoder in encoders.items():
            full_tokens=len(encoder.encode(baseline.decode('utf-8')))
            compact_tokens=len(encoder.encode(compact.decode('utf-8')))
            token_results[name]=dict(
                full=full_tokens,planner=compact_tokens,
                saved=full_tokens-compact_tokens,
                saved_pct=round(100*(1-compact_tokens/full_tokens),2))
        cases.append(dict(
            case=label,queries=number,exact_host_controls=full['counts']['exact_host_controls'],
            full_bytes=len(baseline),planner_bytes=len(compact),
            byte_savings_pct=round(100*(1-len(compact)/len(baseline)),2),
            tokenizer_tokens=token_results,
            projection_encode_median_ms=round(median(timings),5),
            parity=dict(
                snapshot_hash_preserved=(smaller['snapshot_sha256']==full['snapshot_sha256']),
                all_routes_preserved=(
                    [r[1] for r in smaller['rows']] ==
                    [r['route'] for r in full['routes']]),
                denies_action=(smaller['planner_only'] and
                    smaller['authorization_granted'] is False and
                    smaller['executed_actions'] is False and
                    smaller['action_sequence_authorized'] is False and
                    smaller['requires_live_host_check'] is True))))
    aggregate={}
    for name in encoders:
        full=sum(c['tokenizer_tokens'][name]['full'] for c in cases)
        smaller=sum(c['tokenizer_tokens'][name]['planner'] for c in cases)
        aggregate[name]=dict(full=full,planner=smaller,
                             saved_pct=round(100*(1-smaller/full),2))
    if not all(all(c['parity'].values()) for c in cases):
        raise AssertionError('Compact planner projection failed safety/parity')
    return dict(
        format='tavi-observe-planner-tokens-benchmark-v1',
        scope='Fixed synthetic host observations, 1–16 targets, true offline tokenizer encodings. No real model usage, no hosted calls or action execution.',
        iterations_per_case=iterations,
        tokenizer_method='tiktoken offline BPE count of compact JSON only',
        hosted_model_calls=0,
        actual_provider_usage_measured=False,
        baseline='full tavi-observe-route-v1',
        candidate='planner-only tavi-observe-planner-v1',
        aggregate_equal_case_weight=aggregate,cases=cases,
        correctness_verified=True,action_policy_unchanged=True)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iterations',type=int,default=60)
    parser.add_argument('--output',type=Path,help='NEW JSON artifact; never overwrite')
    args=parser.parse_args(argv)
    result=benchmark(iterations=args.iterations)
    if args.output:
        with args.output.open('x',encoding='utf-8') as file:
            json.dump(result,file,indent=2)
            file.write('\n')
    print(json.dumps(result,indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
