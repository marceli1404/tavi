"""Freeze authored layouts, run actual Windows OCR, train/check a separate target model on CPU."""
from concurrent.futures import ThreadPoolExecutor
import argparse
import hashlib
import json
from pathlib import Path
import random
import numpy as np
from tavi_target import VERSION,FEATURES,candidates,sigmoid
from tavi_vision import local_ocr

def save(path,value): path.write_text(json.dumps(value,indent=2),encoding='utf-8')
def metrics(labels,p):
    y=np.array(labels); p=np.clip(np.array(p),1e-7,1-1e-7)
    return dict(n=len(y),positive=int(y.sum()),accuracy=float(np.mean((p>=.5)==y)),
        nll=float(np.mean(-y*np.log(p)-(1-y)*np.log(1-p))),brier=float(np.mean((p-y)**2)))

def freeze(root):
    from PIL import Image,ImageDraw,ImageFont
    root.mkdir(parents=True,exist_ok=False)
    manifest=[]
    # Layout seeds are disjoint by split. Labels are only ground-truth rendered control boxes.
    for split,count,seedbase in [('train',72,41000),('calibration',24,51000),('check',24,61000)]:
        for index in range(count):
            seed=seedbase+index; rng=random.Random(seed)
            target=rng.choice(['Go','Install','Next','Open','Save','Continue'])
            kind=index%4 # plain button; target also in prose; duplicate contexts; disabled/no valid control
            image=Image.new('RGB',(1200,700),rng.choice(['#f7f7f2','#ffffff','#e9edf0']))
            draw=ImageDraw.Draw(image)
            font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',rng.choice([28,32,36,40]))
            draw.text((45,35),'Task workspace',font=font,fill='#20231d')
            boxes=[]
            def button(x,y,label,enabled=True):
                box=[x,y,x+280,y+82]
                draw.rounded_rectangle(box,radius=rng.choice([8,14,20]),fill=rng.choice(['#20231d','#174a7e','#34553a']) if enabled else '#c5c7c5')
                draw.text((x+140,y+41),label,font=font,fill='white' if enabled else '#888888',anchor='mm')
                return box
            x=rng.randint(75,190); y=rng.randint(240,390)
            task=f'Press {target}'
            if kind==0: boxes=[button(x,y,target)]
            elif kind==1:
                draw.text((650,180),target,font=font,fill='#20231d')
                draw.text((650,225),'Documentation example',font=font,fill='#20231d')
                boxes=[button(x,y,target)]
            elif kind==2:
                contexts=rng.sample(['Active workspace','Archived projects','Personal notes','Team drafts'],2)
                chosen=rng.randrange(2)
                for side,context in enumerate(contexts):
                    bx=70+side*570
                    draw.text((bx,200),context,font=font,fill='#20231d')
                    box=button(bx,340,target)
                    if side==chosen: boxes.append(box)
                task=f'Press {target} in {contexts[chosen]}'
            else:
                if index%8==3:
                    button(x,y,target,enabled=False)
                    draw.text((x,y+105),'Disabled',font=font,fill='#20231d')
                else:
                    draw.text((x,y),target,font=font,fill='#20231d')
                    draw.text((x,y+60),'Documentation example',font=font,fill='#20231d')
            path=root/f'{split}-{index:03}.png'; image.save(path)
            manifest.append(dict(split=split,id=f'{split}-{index:03}',seed=seed,file=path.name,target=target,task=task,
                                 correct_boxes=boxes,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    save(root/'manifest.json',{'scope':'authored synthetic UI control-target labels, not real action outcomes',
        'features':FEATURES,'feature_version':VERSION,'cases':manifest,
        'fixed_gate':{'check_accuracy_min':.85,'high_confidence_precision_min':.95,'high_confidence_min_count':8,'proposal_threshold':.9}})
    print(json.dumps({'frozen_layouts':len(manifest),'directory':str(root)}),flush=True)

def extract(root):
    manifest=json.loads((root/'manifest.json').read_text())
    assert not (root/'dataset.json').exists(),'Do not replace extracted evidence'
    def process(case):
        image=root/case['file']
        assert hashlib.sha256(image.read_bytes()).hexdigest()==case['sha256']
        ocr=local_ocr(image)
        if ocr.get('status')!='available': raise RuntimeError('Real Windows OCR required for training')
        items=candidates(image,ocr,case['task'],case['target'])
        rows=[]
        for item in items:
            label=int(any(b[0]<=item['x']<=b[2] and b[1]<=item['y']<=b[3] for b in case['correct_boxes']))
            rows.append(dict(case_id=case['id'],split=case['split'],features=item['features'],label=label,
                             candidate=item['id'],context=item['context']))
        return dict(case=case,ocr=ocr,candidates=items,rows=rows)
    records=[]
    with ThreadPoolExecutor(max_workers=2) as pool:
        for record in pool.map(process,manifest['cases']):
            records.append(record)
            if len(records)%12==0: print(json.dumps({'ocr_layouts':len(records),'total':len(manifest['cases'])}),flush=True)
    save(root/'dataset.json',dict(manifest_sha256=hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest(),records=records))

def train(root,destination):
    destination.mkdir(parents=True,exist_ok=False)
    data=json.loads((root/'dataset.json').read_text())
    manifest=json.loads((root/'manifest.json').read_text())
    assert data['manifest_sha256']==hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest()
    scope_kind=manifest.get('scope_kind','synthetic')
    if scope_kind not in ('synthetic','browser_dom'):
        raise ValueError('Unknown target-label provenance')
    rows=[row for record in data['records'] for row in record['rows']]
    def split(name):
        selected=[r for r in rows if r['split']==name]
        return np.array([r['features'] for r in selected]),np.array([r['label'] for r in selected],dtype=float)
    x,y=split('train'); xc,yc=split('calibration'); xt,yt=split('check')
    mean=x.mean(axis=0); scale=np.maximum(x.std(axis=0),.03)
    x=(x-mean)/scale; xc=(xc-mean)/scale; xt=(xt-mean)/scale
    weight=np.zeros(x.shape[1]); bias=0.; mw=np.zeros_like(weight); vw=np.zeros_like(weight); mb=vb=0.
    # Fixed iteration count and regularization. Check labels never select training parameters.
    for epoch in range(1,1201):
        error=sigmoid(x@weight+bias)-y
        gradient=x.T@error/len(y)+.006*weight; gb=float(error.mean())
        mw=.9*mw+.1*gradient; vw=.999*vw+.001*gradient**2; mb=.9*mb+.1*gb; vb=.999*vb+.001*gb**2
        weight-=.025*(mw/(1-.9**epoch))/(np.sqrt(vw/(1-.999**epoch))+1e-8)
        bias-=.025*(mb/(1-.9**epoch))/(np.sqrt(vb/(1-.999**epoch))+1e-8)
    temperature=min(np.exp(np.linspace(np.log(.5),np.log(4),160)),key=lambda t:metrics(yc,sigmoid((xc@weight+bias)/t))['nll'])
    raw=metrics(yt,sigmoid(xt@weight+bias)); calibrated=metrics(yt,sigmoid((xt@weight+bias)/temperature))
    calraw=metrics(yc,sigmoid(xc@weight+bias)); cal=metrics(yc,sigmoid((xc@weight+bias)/temperature))
    calibration_ok=cal['nll']<=calraw['nll'] and cal['brier']<=calraw['brier'] and calibrated['nll']<=raw['nll'] and calibrated['brier']<=raw['brier']
    if not calibration_ok: temperature=1.
    probability=sigmoid((xt@weight+bias)/temperature)
    check=metrics(yt,probability)
    high=probability>=.9
    high_precision=float(yt[high].mean()) if high.any() else 0.
    accepted=check['accuracy']>=.85 and high.sum()>=8 and high_precision>=.95
    np.savez(destination/'weights.npz',mean=mean,scale=scale,weight=weight,bias=np.array(bias))
    report=dict(train=metrics(y,sigmoid(x@weight+bias)),calibration_raw=calraw,calibration_candidate=cal,
        check_raw=raw,check_candidate=calibrated,check_applied=check,temperature=float(temperature),
        calibration_applied=bool(calibration_ok),high_confidence_count=int(high.sum()),high_confidence_precision=high_precision,
        accepted=bool(accepted),layout_counts={s:sum(r['case']['split']==s for r in data['records']) for s in ('train','calibration','check')},
        dataset_sha256=hashlib.sha256((root/'dataset.json').read_bytes()).hexdigest(),
        missing_ocr_targets=sum(not record['rows'] for record in data['records']))
    save(destination/'evaluation.json',report)
    scope='synthetic_control_target_match' if scope_kind=='synthetic' else 'browser_dom_control_target_match'
    label='synthetic_policy_calibrated' if scope_kind=='synthetic' else 'browser_dom_target_calibrated'
    limits=['Same-author synthetic layouts, not field/task-success labels.'] if scope_kind=='synthetic' else ['Browser DOM target identity, not human/task-success labels; observations clustered by site.']
    save(destination/'model.json',dict(version='screen-target-v1' if scope_kind=='synthetic' else 'screen-target-browser-candidate',feature_version=VERSION,features=FEATURES,
        weights_sha256=hashlib.sha256((destination/'weights.npz').read_bytes()).hexdigest(),accepted=bool(accepted),
        temperature=float(temperature),proposal_threshold=.9,scope=scope,
        probability_status=label if calibration_ok else 'uncalibrated_model_score',
        check_evidence=check,high_confidence_count=int(high.sum()),high_confidence_precision=high_precision,
        limits=limits+['Not probability that clicking is safe or authorized.','Candidate-conditioned; OCR may miss a target completely.']))
    print(json.dumps(report),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--extract',action='store_true')
    parser.add_argument('--train',type=Path)
    args=parser.parse_args()
    if args.prepare: freeze(args.directory)
    if args.extract: extract(args.directory)
    if args.train: train(args.directory,args.train)
