"""Train new label classifiers while preserving all accepted base computations."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS', '2')
import copy
import hashlib
import json
from pathlib import Path
import numpy as np
from tavi_model import DecisionModel, Vectorizer, sigmoid
from training.extensions import records


def train_expansion(base_dir, skills, output):
    base_dir, output = Path(base_dir), Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError('Expansion output must be a new/empty directory')
    base = DecisionModel.load(base_dir)
    existing = base.metadata.get('extensions', [base.metadata['extension']] if base.metadata.get('extension') else [])
    new_names = sorted({s['name'] for s in skills} - set(base.metadata['skills']))
    if not new_names:
        raise ValueError('No new skill names to learn')
    original_rows = json.loads((base_dir/'dataset.json').read_text(encoding='utf-8'))
    extra = records(new_names)
    for skill in skills:
        if skill['name'] in new_names:
            extra.append(dict(id='metadata-'+skill['id'], prompt=skill['name'].replace('-', ' ')+' '+skill['description'],
                              tier=None, skills=[skill['name']], external=False, split='train', origin='weak-skill-metadata'))
    rows = original_rows + extra
    if len({r['prompt'].strip().lower() for r in rows}) != len(rows):
        raise ValueError('Expansion data has duplicate prompts')
    training = [r for r in rows if r['split'] == 'train']
    validation = [r for r in rows if r['split'] == 'validation']
    vectorizer = Vectorizer.fit([r['prompt'] for r in training])
    x = vectorizer.transform([r['prompt'] for r in training])
    vx = vectorizer.transform([r['prompt'] for r in validation])
    y = np.array([[name in r['skills'] for name in new_names] for r in training], dtype='float32')
    vy = np.array([[name in r['skills'] for name in new_names] for r in validation], dtype='float32')
    rng = np.random.default_rng(20261028)
    weight = rng.normal(0, .01, (x.shape[1], len(new_names))).astype('float32')
    bias = np.full(len(new_names), -2., dtype='float32')
    pos_weights = np.minimum(40, (len(training)-y.sum(axis=0))/np.maximum(y.sum(axis=0),1))
    sample_weights = np.where(y>.5, pos_weights, 1)
    mw, vw, mb, vb = np.zeros_like(weight), np.zeros_like(weight), np.zeros_like(bias), np.zeros_like(bias)
    losses = []
    for epoch in range(1, 501):
        predicted = sigmoid(x @ weight + bias)
        delta = (predicted-y)*sample_weights/len(training)
        gw, gb = x.T @ delta + .001*weight, delta.sum(axis=0)
        mw, vw = .9*mw+.1*gw, .999*vw+.001*gw**2
        mb, vb = .9*mb+.1*gb, .999*vb+.001*gb**2
        weight -= .025*(mw/(1-.9**epoch))/(np.sqrt(vw/(1-.999**epoch))+1e-8)
        bias -= .025*(mb/(1-.9**epoch))/(np.sqrt(vb/(1-.999**epoch))+1e-8)
        if epoch in (1,100,250,500):
            loss = float((-sample_weights*(y*np.log(predicted+1e-7)+(1-y)*np.log(1-predicted+1e-7))).mean())
            losses.append(dict(epoch=epoch, loss=loss))
    validation_scores = sigmoid(vx @ weight + bias)
    thresholds, validation_metrics = [], []
    for col, name in enumerate(new_names):
        # Require validation positives before treating a new head as selection-ready.
        if vy[:,col].sum() == 0:
            thresholds.append(1.)
            validation_metrics.append(dict(name=name, ready=False, reason='No labelled validation positives'))
            continue
        trials = []
        for threshold in np.arange(.1,.951,.025):
            selected = validation_scores[:,col] >= threshold
            tp = float((selected*vy[:,col]).sum())
            fp = float((selected*(1-vy[:,col])).sum())
            recall = float(tp/max(float(vy[:,col].sum()),1))
            precision = tp/max(tp+fp,1)
            f1 = 2*precision*recall/max(precision+recall,1e-8)
            trials.append((f1, precision, float(threshold), recall))
        f1, precision, threshold, recall = max(trials)
        thresholds.append(threshold)
        validation_metrics.append(dict(name=name, ready=True, f1=f1, precision=precision, recall=recall))
    metadata = copy.deepcopy(base.metadata)
    metadata['skills'] += new_names
    metadata['format'] = 'tavi-neural-expanded-v1'
    key = 'extension' if not existing else 'extension'+str(len(existing)+1)
    branch = dict(names=new_names, vocabulary=vectorizer.vocabulary, thresholds=thresholds,
                                  base_skills=len(base.metadata['skills']), base_weights_sha256=base.metadata['weights_sha256'],
                                  training_rows=len(training), validation_rows=len(validation), validation=validation_metrics,
                                  array_prefix=key,
                                  architecture='Independent TF-IDF logistic classifiers; original neural arrays and vocabulary frozen')
    metadata['extensions'] = copy.deepcopy(existing)+[branch]
    arrays = {k:v.copy() for k,v in base.arrays.items()}
    arrays.update({key+'_W':weight, key+'_b':bias, key+'_idf':vectorizer.idf})
    metadata['parameters'] = base.metadata['parameters']+weight.size+bias.size
    output.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output/'weights.npz', **arrays)
    metadata['weights_sha256'] = hashlib.sha256((output/'weights.npz').read_bytes()).hexdigest()
    (output/'model.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    payload = json.dumps(rows,indent=2,ensure_ascii=False).encode('utf-8')
    (output/'dataset.json').write_bytes(payload)
    report = dict(strategy='frozen-base-expansion', base_model=str(base_dir.resolve()),
                  base_weights_sha256=base.metadata['weights_sha256'], weights_sha256=metadata['weights_sha256'],
                  new_skills=new_names, parameters=metadata['parameters'], losses=losses,
                  validation=validation_metrics, dataset_sha256=hashlib.sha256(payload).hexdigest())
    (output/'training-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report
