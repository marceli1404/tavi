"""Paired, real Tavi CPU prediction latency benchmark.

This benchmarks Python startup + verified weight loading + inference for
one-shot requests against one persistent offline prediction process.
No computer-use actions, hosted calls, or LLM token costs are measured.
"""
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
TAVI = ROOT/'tavi.py'
PROMPTS = (
    'Fix a mobile navigation layout',
    'Investigate a Python runtime error',
    'Make this responsive landing page accessible',
    'Review database schema and relationships',
    'Write a weekly progress summary',
    'Check CSS breakpoints on a small screen',
    'Design a focused unit test for this parser',
    'Suggest installed skills for website performance',
    'Explain a simple mathematical expression',
    'Review a concurrency race condition',
    'def add(a, b):\n    """Return the sum."""\n    return a + b',
    'Review a security warning without applying changes',
)


def ms(since):
    return (time.perf_counter() - since)*1000


def median(values):
    return round(statistics.median(values), 3)


def main():
    # Stream starts exactly once, then receives multiple fresh independent
    # requests. Never memoize prompts or model predictions in the runner.
    started = time.perf_counter()
    worker = subprocess.Popen(
        [sys.executable, '-u', str(TAVI), 'predict-stream'],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding='utf-8', cwd=ROOT)
    cold_times, warm_times = [], []
    matched = True
    try:
        ready = json.loads(worker.stdout.readline())
        startup_ms = ms(started)
        if ready.get('status') != 'ready':
            raise RuntimeError('Prediction stream did not become ready')
        for index, prompt in enumerate(PROMPTS):
            packet = json.dumps(dict(id=str(index), prompt=prompt), ensure_ascii=False)
            def warm():
                start = time.perf_counter()
                worker.stdin.write(packet+'\n'); worker.stdin.flush()
                line = worker.stdout.readline()
                if not line:
                    raise RuntimeError('Prediction stream terminated unexpectedly')
                return json.loads(line), ms(start)
            def cold():
                start = time.perf_counter()
                proc = subprocess.run(
                    [sys.executable, str(TAVI), 'predict', prompt],
                    cwd=ROOT, text=True, encoding='utf-8',
                    capture_output=True, check=True)
                return json.loads(proc.stdout), ms(start)
            # Alternate order so cold subprocess CPU pressure is not always
            # biased before/after a warm prediction.
            if index % 2 == 0:
                one_shot, cold_ms = cold()
                streamed, warm_ms = warm()
            else:
                streamed, warm_ms = warm()
                one_shot, cold_ms = cold()
            if streamed.get('status') != 'predicted':
                raise RuntimeError(f'Stream prediction failed at case {index}')
            matched &= streamed['prediction'] == one_shot
            cold_times.append(cold_ms); warm_times.append(warm_ms)
        worker.stdin.close()
        code = worker.wait(timeout=10)
        if code:
            raise RuntimeError('Stream ended with an error: '+worker.stderr.read()[-4000:])
    finally:
        if worker.poll() is None:
            worker.kill()
            worker.wait()
        worker.stdout.close()
        worker.stderr.close()
        if not worker.stdin.closed:
            worker.stdin.close()
    if not matched:
        raise AssertionError('Warm and one-shot predictions differ')
    report = dict(
        format='tavi-warm-prediction-benchmark-v1',
        scope='Paired synthetic/offline CPU prompts; process startup and local model load included only in cold per-request calls.',
        cases=len(PROMPTS), warm_startup_ms=round(startup_ms, 3),
        cold_median_ms=median(cold_times), warm_median_ms=median(warm_times),
        speedup_median_ratio=round(statistics.median(cold_times)/statistics.median(warm_times), 2),
        cold_min_ms=round(min(cold_times),3), warm_max_ms=round(max(warm_times),3),
        predictions_equal=True, hosted_calls=0, model_tokens_measured=False,
        end_to_end_computer_use_measured=False)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
