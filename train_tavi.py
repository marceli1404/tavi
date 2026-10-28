"""Reproducible CPU training; does not read acceptance test examples."""
import os
os.environ['OPENBLAS_NUM_THREADS'] = '2'
os.environ['OMP_NUM_THREADS'] = '2'
import argparse
import hashlib
import json
from pathlib import Path
from training.corpus import records
from tavi import scan_skills
from tavi_model import train

BASE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=BASE/'tavi.config.json')
    parser.add_argument('--output', type=Path, default=BASE/'models/tavi-v1')
    parser.add_argument('--epochs', type=int, default=240)
    parser.add_argument('--dataset', type=Path, help='Reproduce training from a saved dataset.json instead of current inventory')
    parser.add_argument('--feedback', type=Path, help='Optional directory of explicitly operator-labelled feedback events')
    args = parser.parse_args()
    if not 1 <= args.epochs <= 2000:
        parser.error('--epochs must be between1 and2000')
    if args.output.exists() and any(args.output.iterdir()):
        parser.error('Output directory is not empty; use a NEW --output directory to preserve existing models')
    if args.dataset:
        rows = json.loads(args.dataset.read_text(encoding='utf-8'))
        skill_names = sorted({name for r in rows for name in r['skills']})
    else:
        config = json.loads(args.config.read_text(encoding='utf-8-sig'))
        skills = scan_skills(config['skill_roots'])
        skill_names = sorted({s['name'] for s in skills})
        rows = records()
        unknown = {name for r in rows for name in r['skills']} - set(skill_names)
        if unknown:
            raise ValueError(f'Labelled skills missing from configured inventory: {unknown}')
        # Weak positives from deployment-visible metadata. No tier label is inferred.
        for skill in skills:
            rows.append(dict(id='metadata-'+skill['id'], prompt=skill['name'].replace('-', ' ')+' '+skill['description'],
                             tier=None, skills=[skill['name']], external=False, split='train', origin='weak-skill-metadata'))
    if args.feedback:
        # Multiple observations may exist; only latest explicitly labelled event per prompt is used.
        events = [json.loads(p.read_text(encoding='utf-8')) for p in sorted(args.feedback.glob('*.json'))]
        latest = {}
        for event in sorted(events, key=lambda e:e['timestamp']):
            latest[event['prompt']] = event
        rows = [r for r in rows if r['prompt'] not in latest] + list(latest.values())
        skill_names = sorted(set(skill_names) | {name for r in rows for name in r['skills']})
    signatures = {}
    for row in rows:
        text = ' '.join(row['prompt'].lower().split())
        if text in signatures:
            raise ValueError('Duplicate prompt in training/validation: '+text)
        signatures[text] = row['split']
    args.output.mkdir(parents=True, exist_ok=True)
    # Persist exact inputs so training can be audited and reconstructed.
    payload = json.dumps(rows, indent=2, ensure_ascii=False).encode('utf-8')
    (args.output/'dataset.json').write_bytes(payload)
    model, losses = train(rows, skill_names, args.output, args.epochs)
    report = dict(dataset_sha256=hashlib.sha256(payload).hexdigest(), losses=losses,
                  training_rows=model.metadata['training_rows'], validation_rows=model.metadata['validation_rows'],
                  parameters=model.metadata['parameters'], weights_sha256=model.metadata['weights_sha256'])
    (args.output/'training-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
