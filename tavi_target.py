"""Learned OCR candidate confidence. This estimates target identity, never action safety."""
import hashlib
import json
from pathlib import Path
import re
import numpy as np

VERSION='target-features-1'
DEFAULT=Path(__file__).resolve().parent/'models/screen-target-v1'
STOP=set('a an the in on at to of for please find locate click press button control return exactly one target candidate its center and whether should i'.split())
FEATURES=['match_count','width','height','background_difference','ring_variance','ink_contrast',
          'context_overlap','context_negative','background_x_context','word_aspect','context_present']

def tokens(text): return set(re.findall(r'[a-z0-9]+',text.casefold()))-STOP

def candidates(image,ocr,task,target):
    from PIL import Image
    if not target or not target.strip() or len(target)>80:
        raise ValueError('An explicit visible target word of1–80 characters is required')
    with Image.open(image) as original, original.convert('RGB') as rgb:
        return _candidates_rgb(rgb,ocr,task,target)


def _candidates_rgb(rgb,ocr,task,target):
    # Keep the decoded bitmap in byte form. Only sampled regions need float64;
    # full-frame float conversion does not contribute any other target feature.
    words=ocr.get('words',[]) if ocr.get('status')=='available' else []
    width,height=rgb.size
    valid=[]
    for word in words:
        try:
            x,y,w,h=(float(word[k]) for k in ('x','y','width','height'))
            if not np.isfinite([x,y,w,h]).all() or min(w,h)<=0 or min(x,y)<0 or x+w>width or y+h>height:
                continue
            if isinstance(word['text'],str): valid.append(dict(text=word['text'],x=x,y=y,width=w,height=h))
        except (ValueError,KeyError,TypeError): continue
    matches=[word for word in valid if word['text'].casefold()==target.strip().casefold()]
    desired=tokens(task)-tokens(target)
    background=np.median(np.asarray(rgb.crop((0,0,min(20,width),min(20,height))),dtype=float)/255,axis=(0,1))
    result=[]
    for index,word in enumerate(matches):
        x,y,w,h=(word[k] for k in ('x','y','width','height'))
        cx,cy=x+w/2,y+h/2
        nearby=[v for v in valid if abs(v['x']+v['width']/2-cx)<320 and abs(v['y']+v['height']/2-cy)<210]
        nearby.sort(key=lambda v:(round(v['y']/12),v['x']))
        context=' '.join(v['text'] for v in nearby)[:700]
        overlap=len(desired&tokens(context))/len(desired) if desired else 1.
        x0,x1=max(0,int(x)-12),min(width,int(x+w)+12)
        y0,y1=max(0,int(y)-10),min(height,int(y+h)+10)
        patch=np.asarray(rgb.crop((x0,y0,x1,y1)),dtype=float)/255
        yy,xx=np.mgrid[y0:y1,x0:x1]
        outside=(xx<x)|(xx>=x+w)|(yy<y)|(yy>=y+h)
        ring=patch[outside]
        ink=np.asarray(rgb.crop((int(x),int(y),max(int(x)+1,int(x+w)),max(int(y)+1,int(y+h)))),dtype=float)/255
        if ink.shape[0]>1 and ink.shape[1]<width:
            # The old full-frame slice was row-strided. Preserve NumPy's
            # reduction path (and exact float64 rounding) with one padding
            # column, rather than allocating full-width floating-point rows.
            padded=np.empty((ink.shape[0],ink.shape[1]+1,3),dtype=float)
            strided=padded[:,:ink.shape[1]]
            strided[:]=ink
            ink=strided
        mean=ring.mean(axis=0) if len(ring) else background
        difference=float(np.sqrt(np.mean((mean-background)**2)))
        negative=bool(tokens(context)&{'disabled','unavailable','inactive'})
        features=[min(len(matches),5)/5,w/width,h/height,difference,float(ring.std()) if len(ring) else 0.,
                  float(np.mean(ink)-np.mean(mean)),overlap,float(negative),difference*overlap,w/max(h,1)/10,float(bool(nearby))]
        result.append(dict(id=f'candidate-{index}',label=word['text'],x=cx,y=cy,box=[x,y,x+w,y+h],
                           context=context,features=features,context_overlap=overlap))
    return result

def sigmoid(x): return 1/(1+np.exp(-np.clip(x,-40,40)))

def load(directory=DEFAULT):
    directory=Path(directory)
    metadata=json.loads((directory/'model.json').read_text(encoding='utf-8'))
    data=(directory/'weights.npz').read_bytes()
    if metadata['feature_version']!=VERSION or metadata['features']!=FEATURES or hashlib.sha256(data).hexdigest()!=metadata['weights_sha256']:
        raise ValueError('Target confidence artifact integrity check failed')
    with np.load(directory/'weights.npz',allow_pickle=False) as saved: arrays={key:saved[key].copy() for key in saved.files}
    if not metadata.get('accepted'):
        raise ValueError('Target confidence candidate was not accepted')
    if set(arrays)!={'mean','scale','weight','bias'} or any(arrays[k].shape!=(len(FEATURES),) for k in ('mean','scale','weight')) or arrays['bias'].shape!=():
        raise ValueError('Invalid target model shape')
    if not all(np.isfinite(v).all() for v in arrays.values()) or np.any(arrays['scale']<=0):
        raise ValueError('Invalid target model values')
    if not np.isfinite(metadata['temperature']) or metadata['temperature']<=0 or not .5<=metadata['proposal_threshold']<1:
        raise ValueError('Invalid confidence settings')
    # Target identity percentages trained on synthetic controls must not qualify
    # automatic actions after a failed real-screen audit. Keep review available.
    audit_path=directory/'field-evaluation.json'
    metadata['automatic_probability_qualified']=False
    if audit_path.exists():
        audit=json.loads(audit_path.read_text(encoding='utf-8'))
        if (audit.get('format')!='tavi-target-field-audit-v1' or
            audit.get('weights_sha256')!=metadata['weights_sha256'] or
            audit.get('status') not in ('failed','insufficient') or
            audit.get('automatic_probability_qualified') is not False):
            raise ValueError('Invalid or mismatched target field audit')
        metadata['field_evaluation']=audit
    return metadata,arrays

def score(items,directory=DEFAULT):
    metadata,arrays=load(directory)
    for item in items:
        x=(np.array(item['features'])-arrays['mean'])/arrays['scale']
        logit=float(x@arrays['weight']+arrays['bias'].item())
        probability=float(sigmoid(logit/metadata['temperature']))
        item['probability']=probability
        # Avoid rounding an estimate to a displayed guarantee of100%.
        item['confidence_percent']=min(99.9,round(100*probability,1))
    items.sort(key=lambda item:-item['probability'])
    return items,metadata
