"""Exhaustive recorded task/target differential check; not an accuracy evaluation."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
import tavi_target


def run(dataset,baseline,output):
    output.mkdir(exist_ok=False)
    assert hashlib.sha256(baseline.read_bytes()).hexdigest()=='abe870f5a1888adbbe4b77e3cdf803e17f8705f88d862662ff80eb71c7d0f8c4'
    spec=importlib.util.spec_from_file_location('baseline_target',baseline)
    previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
    data=json.loads((dataset/'dataset.json').read_text())
    protocol=dict(baseline_source_sha256=hashlib.sha256(baseline.read_bytes()).hexdigest(),
                  candidate_source_sha256=hashlib.sha256((BASE/'tavi_target.py').read_bytes()).hexdigest(),
                  dataset_sha256=hashlib.sha256((dataset/'dataset.json').read_bytes()).hexdigest(),
                  scope='Every unique recorded task/target in every training/check/audit screenshot; numerical compatibility only, not independent recognition accuracy.')
    (output/'protocol.json').write_text(json.dumps(protocol,indent=2),encoding='utf-8')
    requests=0;count=0
    for record in data['records']:
        image=dataset/(record['case']['id']+'.png')
        assert hashlib.sha256(image.read_bytes()).hexdigest()==record['sha256']
        for task,target in sorted({(r['task'],r['target']) for r in record['rows']}):
            old=previous.candidates(image,record['ocr'],task,target)
            new=tavi_target.candidates(image,record['ocr'],task,target)
            assert old==new,(record['case']['id'],target,'features')
            a,ma=previous.score(old);b,mb=tavi_target.score(new)
            assert a==b,(record['case']['id'],target,'scores')
            assert ma['weights_sha256']==mb['weights_sha256']
            assert not ma['automatic_probability_qualified'] and not mb['automatic_probability_qualified']
            requests+=1;count+=len(a)
    report=dict(screenshots=len(data['records']),requests=requests,candidates=count,
                feature_score_and_ranking_exact=True,automatic_probability_qualified=False,protocol=protocol)
    (output/'summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('dataset',type=Path);p.add_argument('baseline',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();run(a.dataset,a.baseline,a.output)
