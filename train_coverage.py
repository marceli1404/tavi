"""Train a tier-only residual classifier; no acceptance labels or model-task outcomes."""
import os
os.environ['OPENBLAS_NUM_THREADS']='2'
os.environ['OMP_NUM_THREADS']='2'
import argparse
import copy
import hashlib
import json
import re
from pathlib import Path
import shutil
from tavi_model import DecisionModel, Vectorizer, TIERS, softmax
import numpy as np

BASE=Path(__file__).parent


def train_coverage(base_dir,output,corpus_path=None):
    base_dir,output=Path(base_dir),Path(output)
    if output.exists():raise ValueError('Tier training requires a new output directory')
    original=DecisionModel.load(base_dir)
    if original.metadata.get('tier_adapter'):raise ValueError('Stacked tier adapters are not supported; choose the original base')
    corpus_path=Path(corpus_path or BASE/'training/coverage_corpus-v2.json')
    extra=json.loads(corpus_path.read_text(encoding='utf-8'))
    old=json.loads((base_dir/'dataset.json').read_text(encoding='utf-8'))
    rows=[dict(prompt=r['prompt'],tier=r['tier'],split=r['split'],origin='base-tier') for r in old if r.get('tier') in TIERS]+extra
    if len({r['prompt'].strip().lower() for r in rows})!=len(rows):raise ValueError('Duplicate tier training/validation prompt')
    training=[r for r in rows if r['split']=='train']
    validation=[r for r in rows if r['split']=='validation']
    vector=Vectorizer.fit([r['prompt'] for r in training],limit=6000)
    x=vector.transform([r['prompt'] for r in training])
    vx=vector.transform([r['prompt'] for r in validation])
    logits=np.log(np.maximum(original.predict([r['prompt'] for r in training])[0],1e-12))
    vl=np.log(np.maximum(original.predict([r['prompt'] for r in validation])[0],1e-12))
    y=np.array([TIERS.index(r['tier']) for r in training])
    vy=np.array([TIERS.index(r['tier']) for r in validation])
    target=np.eye(4,dtype=np.float32)[y]
    sample=np.sqrt(len(y)/np.maximum(np.bincount(y,minlength=4),1))[y].astype(np.float32)
    w=np.zeros((x.shape[1],4),dtype=np.float32)
    b=np.zeros(4,dtype=np.float32)
    mw,vw=np.zeros_like(w),np.zeros_like(w)
    mb,vb=np.zeros_like(b),np.zeros_like(b)
    best=None
    trace=[]
    old_validation=np.array([r['origin']=='base-tier' for r in validation])
    new_validation=~old_validation
    original_validation=softmax(vl)
    structured=np.array([bool(re.search(r'(?m)^def\s+\w+\([^\n]*\).*:',r['prompt'])) for r in validation])
    old_accuracy=float((original_validation.argmax(1)[old_validation]==vy[old_validation]).mean())
    for epoch in range(1,401):
        p=softmax(logits+x @ w+b)
        grad=(p-target)*sample[:,None]/sample.sum()
        gw=x.T @ grad+.00003*w
        gb=grad.sum(0)
        mw=.9*mw+.1*gw;vw=.999*vw+.001*gw**2
        mb=.9*mb+.1*gb;vb=.999*vb+.001*gb**2
        w-=.06*(mw/(1-.9**epoch))/(np.sqrt(vw/(1-.999**epoch))+1e-8)
        b-=.06*(mb/(1-.9**epoch))/(np.sqrt(vb/(1-.999**epoch))+1e-8)
        if epoch%10==0:
            vp=softmax(vl+vx @ w+b)
            for gate in (.55,.65,.75,.85,.9,.95,.98,.995,1.):
                apply=(vp.max(1)>=gate)&~(structured&(vp.argmax(1)==3)&(original_validation.argmax(1)!=3)&(original_validation.max(1)>=.5))
                selected=np.where(apply[:,None],vp,original_validation)
                retained=float((selected.argmax(1)[old_validation]==vy[old_validation]).mean())
                if retained<old_accuracy:continue
                new_accuracy=float((selected.argmax(1)[new_validation]==vy[new_validation]).mean())
                accuracy=float((selected.argmax(1)==vy).mean())
                loss=float(-np.log(np.maximum(selected[np.arange(len(vy)),vy],1e-12)).mean())
                score=(new_accuracy,accuracy,-loss)
                trace.append(dict(epoch=epoch,gate=gate,validation_accuracy=accuracy,validation_nll=loss))
                if best is None or score>best[0]:best=(score,w.copy(),b.copy(),epoch,gate)
    arrays={k:v.copy() for k,v in original.arrays.items()}
    arrays.update(tier_adapter_W=best[1],tier_adapter_b=best[2],tier_adapter_idf=vector.idf)
    metadata=copy.deepcopy(original.metadata)
    metadata['tier_adapter']=dict(vocabulary=vector.vocabulary,source_weights_sha256=original.metadata['weights_sha256'],
        selected_epoch=best[3],train_rows=len(training),validation_rows=len(validation),
        minimum_confidence=best[4],
        preserve_structured_specs=True,
        scope='Residual tier-only TF-IDF classifier; other neural heads and arrays frozen')
    metadata['parameters']=original.metadata['parameters']+best[1].size+best[2].size
    output.mkdir(parents=True)
    np.savez_compressed(output/'weights.npz',**arrays)
    metadata['weights_sha256']=hashlib.sha256((output/'weights.npz').read_bytes()).hexdigest()
    (output/'model.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    shutil.copyfile(base_dir/'dataset.json',output/'dataset.json')
    (output/'tier-dataset.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    report=dict(source_weights_sha256=original.metadata['weights_sha256'],weights_sha256=metadata['weights_sha256'],
                train_cases=len(training),validation_cases=len(validation),selected_epoch=best[3],
                minimum_confidence=best[4],
                corpus_sha256=hashlib.sha256(corpus_path.read_bytes()).hexdigest(),
                no_acceptance_or_outcome_labels_fitted=True,trace=trace)
    (output/'training-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='trace'},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--corpus',type=Path,default=None)
    args=parser.parse_args()
    train_coverage(args.base,args.output,args.corpus)
