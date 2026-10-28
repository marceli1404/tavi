"""Fit a code-context tier head with the accepted v3 network and text adapter frozen."""
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
from tavi_model import DecisionModel,Vectorizer,TIERS,softmax,is_coding_spec
import numpy as np


def train(base_dir,corpus,output):
    base_dir,corpus,output=map(Path,(base_dir,corpus,output))
    if output.exists():raise ValueError('Use a new candidate directory')
    base=DecisionModel.load(base_dir)
    rows=[r for r in json.loads(corpus.read_text()) if r['origin']=='new-authored-structured-code']
    if any(re.search(r'def helper_(?:fast|balanced|deep|review)_',r['prompt']) for r in rows):
        raise ValueError('Synthetic function names expose target labels')
    if not all(is_coding_spec(r['prompt']) for r in rows):raise ValueError('Coding training requires explicit specifications')
    if len({r['prompt'] for r in rows})!=len(rows):raise ValueError('Duplicate coding prompts')
    fit=[r for r in rows if r['split']=='train'];validation=[r for r in rows if r['split']=='validation']
    vector=Vectorizer.fit([r['prompt'] for r in fit],limit=4096)
    x=vector.transform([r['prompt'] for r in fit]);vx=vector.transform([r['prompt'] for r in validation])
    logits=np.log(np.maximum(base.predict([r['prompt'] for r in fit])[0],1e-12))
    original=base.predict([r['prompt'] for r in validation])[0];vl=np.log(np.maximum(original,1e-12))
    y=np.array([TIERS.index(r['tier']) for r in fit]);vy=np.array([TIERS.index(r['tier']) for r in validation])
    target=np.eye(4,dtype=np.float32)[y];sample=np.sqrt(len(y)/np.bincount(y,minlength=4))[y]
    w=np.zeros((x.shape[1],4),dtype=np.float32);b=np.zeros(4,dtype=np.float32)
    mw=np.zeros_like(w);vw=np.zeros_like(w);mb=np.zeros_like(b);vb=np.zeros_like(b)
    best=None;trace=[]
    for epoch in range(1,501):
        p=softmax(logits+x @ w+b);g=(p-target)*sample[:,None]/sample.sum()
        gw=x.T @ g+.00003*w;gb=g.sum(0)
        mw=.9*mw+.1*gw;vw=.999*vw+.001*gw**2;mb=.9*mb+.1*gb;vb=.999*vb+.001*gb**2
        w-=.06*(mw/(1-.9**epoch))/(np.sqrt(vw/(1-.999**epoch))+1e-8)
        b-=.06*(mb/(1-.9**epoch))/(np.sqrt(vb/(1-.999**epoch))+1e-8)
        if epoch%10==0:
            vp=softmax(vl+vx @ w+b)
            for gate in (.55,.65,.75,.85,.95):
                apply=(vp.max(1)>=gate)&~((vp.argmax(1)==3)&(original.argmax(1)!=3)&(original.max(1)>=.5))
                p=np.where(apply[:,None],vp,original)
                macro=float(np.mean([(p.argmax(1)[vy==i]==i).mean() for i in range(4)]))
                nll=float(-np.log(np.maximum(p[np.arange(len(vy)),vy],1e-12)).mean())
                trace.append(dict(epoch=epoch,gate=gate,macro_accuracy=macro,nll=nll))
                score=(macro,-nll)
                if best is None or score>best[0]:best=(score,w.copy(),b.copy(),epoch,gate)
    metadata=copy.deepcopy(base.metadata);arrays={k:v.copy() for k,v in base.arrays.items()}
    arrays.update(coding_adapter_W=best[1],coding_adapter_b=best[2],coding_adapter_idf=vector.idf)
    metadata['coding_adapter']=dict(vocabulary=vector.vocabulary,minimum_confidence=best[4],selected_epoch=best[3],
        source_weights_sha256=base.metadata['weights_sha256'],scope='Learned residual tier scores for explicit Python signature/docstring contexts; non-code predictions frozen')
    metadata['parameters']+=best[1].size+best[2].size
    output.mkdir(parents=True);np.savez_compressed(output/'weights.npz',**arrays)
    metadata['weights_sha256']=hashlib.sha256((output/'weights.npz').read_bytes()).hexdigest()
    (output/'model.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    for filename in ('dataset.json','tier-dataset.json'):
        shutil.copyfile(base_dir/filename,output/filename)
    (output/'coding-dataset.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    report=dict(source_weights_sha256=base.metadata['weights_sha256'],weights_sha256=metadata['weights_sha256'],fit_cases=len(fit),validation_cases=len(validation),
        selected_epoch=best[3],minimum_confidence=best[4],corpus_sha256=hashlib.sha256(corpus.read_bytes()).hexdigest(),trace=trace)
    (output/'coding-training-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='trace'},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',required=True);p.add_argument('--corpus',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();train(a.base,a.corpus,a.output)
