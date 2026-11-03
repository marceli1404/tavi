"""Benchmark safe unscoped lookup indexing without changing control facts.

Both paths validate and hash the full immutable host snapshot. The faster
path simply avoids constructing a never-used context lookup table when all
queries are unscoped; context-scoped requests retain the original index.
No browser, screenshots, hosted model, network or actions are involved.
"""
from __future__ import annotations

from datetime import datetime, timezone
import argparse
import json
import math
from pathlib import Path
from statistics import median
import time

from tavi_controls import ControlIndex, resolve_many


def snapshot(size=2048):
    if type(size) is not int or not 16 <= size <= 10000:
        raise ValueError('size must be an integer between 16 and 10000')
    controls=[]
    for index in range(size):
        controls.append({
            'id':f'control-{index}',
            'label':f'Control number {index}',
            'role':'button',
            'context':f'Subsection {index%64} / Control group {index//64}',
            'visible':True,'enabled':True,
            'bounds':[20+index%20,30+index%20,120,32],
        })
    return {
        'format':'tavi-control-snapshot-v1',
        'source':'supported_browser_dom',
        'snapshot_id':'benchmark-fresh-control-snapshot',
        'captured_at':datetime.now(timezone.utc).isoformat(),
        'viewport':[1024,768],
        'controls':controls,
    }


def queries(size):
    indices=[(size-1-i*max(1,size//32))%size for i in range(16)]
    return [dict(task='Inspect the current control',
                 target=f'Control number {index}',role='button',
                 id=f'query-{i}') for i,index in enumerate(indices)]


def evaluate(state,items,*,context_index,now):
    prepared=ControlIndex(state,context_index=context_index)
    results=[]
    for q in items:
        result=prepared.resolve(q['task'],q['target'],
                                role=q['role'],now=now)
        result['query_id']=q['id']
        results.append(result)
    return prepared.snapshot_sha256,results


def benchmark(*,sizes=(64,512,2048),iterations=35):
    if (not isinstance(sizes,(tuple,list)) or not sizes or
            any(type(n) is not int or not 16<=n<=10000 for n in sizes)
            or type(iterations) is not int or not 5<=iterations<=200):
        raise ValueError('Invalid fixed benchmark configuration')
    cases=[]
    for size in sizes:
        state=snapshot(size)
        items=queries(size)
        now=datetime.now(timezone.utc)
        baseline_digest,baseline=evaluate(state,items,context_index=True,now=now)
        optimized_digest,optimized=evaluate(state,items,context_index=False,now=now)
        actual=resolve_many(state,items,now=now)
        if (baseline_digest!=optimized_digest or baseline_digest!=actual['snapshot_sha256']
            or baseline!=optimized or baseline!=actual['proposals']):
            raise AssertionError('Context-index optimization changed control decisions')
        measurements={'full_context_index':[],'unscoped_only_index':[]}
        for n in range(iterations):
            order=('full_context_index','unscoped_only_index') if n%2==0 else (
                   'unscoped_only_index','full_context_index')
            for variant in order:
                started=time.perf_counter()
                evaluate(state,items,context_index=(variant=='full_context_index'),now=now)
                measurements[variant].append((time.perf_counter()-started)*1000)
        first=median(measurements['full_context_index'])
        second=median(measurements['unscoped_only_index'])
        cases.append(dict(
            controls=size,queries=len(items),
            baseline_full_context_median_ms=round(first,3),
            optimized_unscoped_median_ms=round(second,3),
            median_ratio=round(first/second,3) if second else None,
            snapshot_digest_identical=True,decisions_identical=True,
            full_snapshot_validation_preserved=True,
            mandatory_live_host_check=True,executed_actions=False))
    return dict(
        format='tavi-unscoped-context-index-efficiency-v1',
        scope='Fixed synthetic 64/512/2048 host controls. Index build + 16 queries, same snapshot SHA, deterministic clock, no browser or model.',
        iterations=iterations,cases=cases,all_proposal_decisions_preserved=True,
        source='tavi-controls-index-full-vs-unscoped',hosted_calls=0,
        model_tokens_measured=False,full_browser_task_latency_measured=False)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iterations',type=int,default=35)
    parser.add_argument('--output',type=Path,help='Create a NEW JSON report')
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
