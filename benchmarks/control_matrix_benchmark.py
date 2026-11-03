"""Synthetic, reproducible wire-format benchmark; not a full computer-use score.

Usage: python benchmarks/control_matrix_benchmark.py
Measures JSON UTF-8 payload size and local conversion cost after resolution.
Does not measure LLM tokens, model inference, browser capture or action latency.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tavi_controls import resolve_many
from tavi_control_compact import compact_batch
from tavi_control_matrix import matrix_batch, expand_matrix


def fixture(count=64):
    snapshot = dict(
        format='tavi-control-snapshot-v1', snapshot_id='synthetic-1',
        captured_at=datetime.now(timezone.utc).isoformat(),
        source='supported_browser_dom', viewport=[1440, 900], controls=[
            dict(id=f'control-{i}', label=f'Control {i}', role='button',
                 context='Main toolbar', visible=True, enabled=True,
                 bounds=[10+i, 25, 80, 30]) for i in range(100)])
    queries = [dict(id=f'q{i}', task=f'Find control {i}',
                    target=f'Control {i%100}', role='button', context='Main toolbar')
               for i in range(count)]
    return resolve_many(snapshot, queries)


def wire_size(packet):
    return len(json.dumps(packet, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))


def median_ms(func, batch, iterations=250):
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        func(batch)
        times.append((time.perf_counter()-start)*1000)
    return round(statistics.median(times), 5)


def main():
    batch = fixture()
    compact = compact_batch(batch)
    matrix = matrix_batch(batch)
    assert expand_matrix(matrix) == batch
    sizes = {name: wire_size(packet) for name, packet in
             [('full',batch),('compact',compact),('matrix',matrix)]}
    results = dict(format='tavi-control-matrix-benchmark-v1',
                   scope='Synthetic resolved responses only; 64 queries; no model, capture, click, or API calls.',
                   bytes=sizes,
                   matrix_bytes_saved_vs_full=round(100*(1-sizes['matrix']/sizes['full']), 2),
                   matrix_bytes_saved_vs_compact=round(100*(1-sizes['matrix']/sizes['compact']), 2),
                   conversion_median_ms={'compact':median_ms(compact_batch,batch),
                                         'matrix':median_ms(matrix_batch,batch)},
                   round_trip_equal=True,
                   token_count_measured=False,
                   end_to_end_speedup_measured=False)
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
