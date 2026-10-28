"""CPU expansion CLI used by the guarded refresh pipeline."""
import argparse
import json
from pathlib import Path
from tavi import scan_skills
from tavi_expand import train_expansion


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',type=Path,required=True)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding='utf-8-sig'))
    print(json.dumps(train_expansion(args.base,scan_skills(config['skill_roots']),args.output),indent=2))
