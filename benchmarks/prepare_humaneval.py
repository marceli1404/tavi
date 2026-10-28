"""Fetch a pinned public evaluation subset; never add it to training data."""
import gzip
import hashlib
import json
from pathlib import Path
import urllib.request

BASE = Path(__file__).resolve().parent
IDS = [0,20,56,70,100,132,146,154]


def fetch(url):
    request = urllib.request.Request(url,headers={'User-Agent':'Tavi-outcome-evaluation/0.5'})
    with urllib.request.urlopen(request,timeout=25) as response:
        data = response.read(2_000_001)
    if len(data)>2_000_000:
        raise ValueError('Source exceeds fetch limit')
    return data


def prepare():
    commit = json.loads(fetch('https://api.github.com/repos/openai/human-eval/commits/master'))['sha']
    root = f'https://raw.githubusercontent.com/openai/human-eval/{commit}'
    compressed = fetch(root+'/data/HumanEval.jsonl.gz')
    license_data = fetch(root+'/LICENSE')
    rows = [json.loads(line) for line in gzip.decompress(compressed).decode('utf-8').splitlines()]
    selected = [next(row for row in rows if row['task_id']==f'HumanEval/{i}') for i in IDS]
    provenance = dict(repository='https://github.com/openai/human-eval',commit=commit,
                      source_sha256=hashlib.sha256(compressed).hexdigest(),task_ids=[r['task_id'] for r in selected],
                      license='MIT',scope='Eight fixed public tasks; historical dataset, possible foundation-model pretraining contamination; no Tavi training on these cases')
    destination=BASE/'humaneval'
    destination.mkdir(exist_ok=True)
    (destination/'cases.json').write_text(json.dumps(selected,indent=2),encoding='utf-8')
    (destination/'provenance.json').write_text(json.dumps(provenance,indent=2),encoding='utf-8')
    (destination/'LICENSE').write_bytes(license_data)
    print(json.dumps(provenance,indent=2))
    for row in selected:
        print(row['task_id'],row['entry_point'],len(row['prompt']),row['prompt'][:130].replace('\n',' '))


if __name__ == '__main__':
    prepare()
