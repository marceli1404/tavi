"""Fit on calibration rows, check on separate rows; optional gated sidecar activation."""
import argparse
import json
from pathlib import Path
from tavi_model import DecisionModel
from tavi_probability import fit_calibration


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--cases', type=Path, default=Path(__file__).parent/'training/probability_cases.json')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--activate', action='store_true')
    parser.add_argument('--headwise', action='store_true',help='Validate each head independently; rejected heads retain raw scores and explicit uncalibrated status')
    args = parser.parse_args()
    rows = json.loads(args.cases.read_text(encoding='utf-8'))
    # Include every saved train/validation prompt; frozen benchmark labels are never fitted.
    dataset = json.loads((args.model/'dataset.json').read_text(encoding='utf-8'))
    if (args.model/'tier-dataset.json').is_file():
        dataset += json.loads((args.model/'tier-dataset.json').read_text(encoding='utf-8'))
    if (args.model/'coding-dataset.json').is_file():
        dataset += json.loads((args.model/'coding-dataset.json').read_text(encoding='utf-8'))
    from training.heldout import CASES
    from training.extension_heldout import CASES as EXTENSION_CASES
    excluded = [r['prompt'] for r in dataset]+[r[0] for r in CASES]+[r[0] for r in EXTENSION_CASES]
    model = DecisionModel.load(args.model)
    report = fit_calibration(model, rows, excluded,headwise=args.headwise)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
    if args.activate:
        if not report['accepted']:
            raise ValueError('Calibration check gates failed; report retained, activation refused')
        with (args.model/'probability.json').open('x', encoding='utf-8') as stream:
            json.dump(report, stream, indent=2)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
