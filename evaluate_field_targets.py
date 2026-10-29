"""Readonly browser-labelled target audit. Split by site; no click-safety labels."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import numpy as np
from PIL import Image
from tavi_ocr import OcrSession
from tavi_target import candidates, score
from train_screen_target import metrics


def extract(root):
    output=root/'dataset.json'
    if output.exists():
        raise ValueError('Preserve existing extraction; use a new collection directory')
    records=[]
    with OcrSession() as session:
        for path in sorted(root.glob('*-*.json')):
            facts=json.loads(path.read_text(encoding='utf-8'))
            if 'elements' not in facts: continue
            image=path.with_suffix('.png')
            with Image.open(image) as rendered: size=rendered.size
            sx,sy=size[0]/facts['width'],size[1]/facts['height']
            ocr=session(image)
            # Single-word OCR targets only. Include all visible role-labelled text,
            # rather than selecting examples according to the model's score.
            targets=sorted({word.casefold() for e in facts['elements'] for word in re.findall(r'[A-Za-z][A-Za-z0-9-]*',e['text']) if 2<=len(word)<=30})
            buttons=[e for e in facts['elements'] if e['enabled'] and (e['tag'] in ('BUTTON','INPUT') or e['role']=='button')]
            rows=[]
            for target in targets:
                for item in candidates(image,ocr,'Press '+target,target):
                    hit=any(b['box'][0]*sx<=item['x']<=b['box'][2]*sx and b['box'][1]*sy<=item['y']<=b['box'][3]*sy for b in buttons)
                    rows.append(dict(**{**item,'label':int(hit)},case_id=facts['id'],site=facts['site'],split=facts['split'],target=target,
                                     task='Press '+target))
            records.append(dict(case=facts,image_size=size,dom_to_image_scale=[sx,sy],sha256=hashlib.sha256(image.read_bytes()).hexdigest(),ocr=ocr,rows=rows))
            print(json.dumps({'screen':facts['id'],'candidates':len(rows),'positive':sum(r['label'] for r in rows)}),flush=True)
    output.write_text(json.dumps(dict(protocol_sha256=hashlib.sha256((root/'protocol.json').read_bytes()).hexdigest(),records=records),indent=2),encoding='utf-8')


def audit(root,model,output):
    data=json.loads((root/'dataset.json').read_text(encoding='utf-8'))
    report={}
    predictions=[]
    for split in ('train','calibration','check','audit'):
        rows=[r for record in data['records'] for r in record['rows'] if r['split']==split]
        items=[{**r,'label':r['target']} for r in rows]
        # Score each independently without changing the labels or row order.
        for row,item in zip(rows,items):
            scored,_=score([item],model)
            predictions.append({**row,'probability':scored[0]['probability']})
        selected=[r for r in predictions if r['split']==split]
        y=np.array([r['label'] for r in selected]); p=np.array([r['probability'] for r in selected])
        high=p>=.95
        report[split]=dict(candidates=len(y),**metrics(y,p),
                          high95_count=int(high.sum()),high95_correct=int(y[high].sum()),
                          high95_precision=float(y[high].mean()) if high.any() else None)
    result=dict(scope='Real rendered browser target identity; site-disjoint splits; no action outcome/safety labels.',
                dataset_sha256=hashlib.sha256((root/'dataset.json').read_bytes()).hexdigest(),model=str(model),
                metrics=report,predictions=predictions)
    if output.exists(): raise ValueError('Do not overwrite audit evidence')
    output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(report),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path);p.add_argument('--extract',action='store_true');p.add_argument('--model',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.extract: extract(a.root)
    if a.model: audit(a.root,a.model,a.output)
