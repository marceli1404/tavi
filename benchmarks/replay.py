"""Offline replay of frozen task/role outcomes. Never executes candidate code or APIs."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import statistics


def replay(outcomes, decisions, fallback=None, repetitions=2000, seed=0):
    if not isinstance(repetitions, int) or not 100 <= repetitions <= 100000:
        raise ValueError('bootstrap repetitions must be 100..100000')
    matrix = {}
    for row in outcomes['results']:
        key = (row['task_id'], row['role'])
        if key in matrix:
            raise ValueError('Duplicate task/role outcome: ' + str(key))
        if not all(isinstance(v, str) and v for v in key) or key[1] == 'review':
            raise ValueError('Invalid task/role identifier')
        if type(row['verdict']['passed']) is not bool:
            raise ValueError('Outcome passed must be boolean')
        elapsed = row['elapsed_seconds']
        if isinstance(elapsed, bool) or not isinstance(elapsed, (int, float)) or not math.isfinite(elapsed) or elapsed < 0:
            raise ValueError('Elapsed time must be finite and nonnegative')
        matrix[key] = row
    tasks = sorted({t for t, _ in matrix})
    roles = sorted({r for _, r in matrix})
    if not tasks or any((t, r) not in matrix for t in tasks for r in roles):
        raise ValueError('Outcome matrix must be nonempty and rectangular')
    if fallback is not None and fallback not in roles:
        raise ValueError('Fallback must be an observed role')
    if set(decisions) != set(tasks):
        raise ValueError('Decisions must cover exactly the outcome tasks')
    if any(v not in roles + ['review'] for v in decisions.values()):
        raise ValueError('Unknown route; use review for abstention')

    def metrics(routes):
        selected = [matrix.get((t, routes[t])) for t in tasks]
        passed = [int(r['verdict']['passed']) if r else 0 for r in selected]
        times = [r['elapsed_seconds'] if r else 0 for r in selected]
        return dict(tasks=len(tasks), passed=sum(passed), success_rate=statistics.mean(passed),
                    unresolved=sum(r is None for r in selected),
                    selected_generation_seconds=sum(times)), passed

    resolved = {t: fallback if decisions[t] == 'review' else decisions[t] for t in tasks}
    summary, success = metrics(resolved)
    summary['abstained'] = sum(v == 'review' for v in decisions.values())
    baselines = {}
    rng = random.Random(seed)
    for role in roles:
        static, reference = metrics(dict.fromkeys(tasks, role))
        differences = [a-b for a, b in zip(success, reference)]
        samples = sorted(statistics.mean(rng.choices(differences, k=len(tasks))) for _ in range(repetitions))
        baselines[role] = dict(metrics=static,
            success_difference=statistics.mean(differences),
            paired_bootstrap_95_interval=[samples[int(.025*repetitions)], samples[min(repetitions-1, int(.975*repetitions))]])
    return dict(schema_version=1, summary=summary, static_baselines=baselines,
                fallback=fallback, seed=seed, bootstrap_repetitions=repetitions,
                usd_cost=None, limits=[
                    'Task-level percentile bootstrap assumes independent tasks; not a cluster interval or non-inferiority test.',
                    'One frozen outcome per task/role; no estimate of generation variability.',
                    'Selected generation time excludes router overhead and unresolved-task delay; not end-to-end latency.',
                    'No verified prices; no cheapest/strongest role inferred from names or test outcomes.',
                    'Small public benchmarks do not establish general routing superiority.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--outcomes', type=Path, required=True)
    parser.add_argument('--decisions', type=Path, required=True, help='JSON object mapping task IDs to role or review')
    parser.add_argument('--fallback', help='Observed role used for every review decision; otherwise unresolved is a failure')
    parser.add_argument('--bootstrap', type=int, default=2000)
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raw_outcomes = args.outcomes.read_bytes()
    raw_decisions = args.decisions.read_bytes()
    report = replay(json.loads(raw_outcomes), json.loads(raw_decisions), args.fallback, args.bootstrap, args.seed)
    report['inputs_sha256'] = dict(outcomes=hashlib.sha256(raw_outcomes).hexdigest(), decisions=hashlib.sha256(raw_decisions).hexdigest())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps(report['summary']))


if __name__ == '__main__':
    main()
