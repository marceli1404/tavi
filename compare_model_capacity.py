"""Compare one experimental Tavi model with the frozen baseline; never promote it.

Only compares existing evaluation reports with matching held-out case hashes.
These are same-author synthetic policy tests, not evidence of user task success.
This command never trains, writes model pointers, or changes configuration.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from tavi_model import DecisionModel

COMPARABLE_METRICS = (
    'tier_accuracy', 'skill_recall_at_3', 'external_accuracy',
    'skill_precision', 'skill_recall', 'no_skill_accuracy',
)
REGRESSION_TOLERANCE = .02


def comparison(baseline: Path, candidate: Path) -> dict:
    old = DecisionModel.load(baseline)
    new = DecisionModel.load(candidate)
    if new.metadata.get('experimental_capacity') is not True:
        raise ValueError('Candidate must be an explicitly experimental capacity model')
    if new.metadata['parameters'] <= old.metadata['parameters']:
        raise ValueError('Candidate does not have more trainable parameters than baseline')
    reports = []
    for directory, model in ((baseline, old), (candidate, new)):
        report = json.loads((directory / 'evaluation.json').read_text(encoding='utf-8'))
        if report.get('weights_sha256') != model.metadata['weights_sha256']:
            raise ValueError('Evaluation is not bound to exact model weights: ' + str(directory))
        if report.get('cases') != 50:
            raise ValueError('Expected complete 50-case synthetic heldout evaluation')
        if any(name not in report.get('metrics', {}) for name in COMPARABLE_METRICS):
            raise ValueError('Missing comparable acceptance metric')
        reports.append(report)
    a, b = reports
    if a.get('acceptance_source_sha256') != b.get('acceptance_source_sha256'):
        raise ValueError('Different heldout evaluation sources cannot be compared')
    differences = {
        key: round(b['metrics'][key] - a['metrics'][key], 6)
        for key in COMPARABLE_METRICS
    }
    regressions = [key for key, delta in differences.items() if delta < -REGRESSION_TOLERANCE]
    return {
        'status': 'review_required',
        'scope': 'Same-author synthetic acceptance tasks; no real Codex outcomes or independent field calibration',
        'baseline': {'path': str(baseline), 'parameters': old.metadata['parameters'],
                     'weights_sha256': old.metadata['weights_sha256']},
        'candidate': {'path': str(candidate), 'parameters': new.metadata['parameters'],
                      'weights_sha256': new.metadata['weights_sha256'],
                      'capacity': new.metadata.get('capacity')},
        'parameter_multiplier': round(new.metadata['parameters'] / old.metadata['parameters'], 3),
        'heldout_cases': 50,
        'metric_deltas_candidate_minus_baseline': differences,
        'regressions_over_two_percentage_points': regressions,
        'synthetic_gates_passed': b.get('passed') is True,
        'synthetic_nonregression_passed': not regressions,
        'recommendation': ('independent_field_review_needed'
                           if b.get('passed') is True and not regressions
                           else 'retain_baseline'),
        'automatically_activated': False,
        'can_replace_default_without_review': False,
        'timing_note': 'Stored inference times from different machines are not compared',
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path,
                        default=Path(__file__).parent/'models/tavi-v4-clean')
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--output', type=Path, help='Write report to a NEW JSON file only')
    args = parser.parse_args(argv)
    report = comparison(args.baseline, args.candidate)
    if args.output:
        with args.output.open('x', encoding='utf-8') as out:
            json.dump(report, out, indent=2)
    print(json.dumps(report, indent=2))
    return 0 if report['synthetic_gates_passed'] and report['synthetic_nonregression_passed'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
