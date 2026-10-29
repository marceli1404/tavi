"""Tavi's original CPU neural decision model; no pretrained model or API calls."""
from __future__ import annotations
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS', '2')
os.environ.setdefault('OMP_NUM_THREADS', '2')
import hashlib
import json
from pathlib import Path
import re
import numpy as np

TIERS = ['fast', 'balanced', 'deep', 'review']


def words(text):
    terms = re.findall(r'[a-z][a-z0-9]+', text.lower())
    return [w[:-1] if len(w) > 4 and w.endswith('s') else w for w in terms]


def features(text):
    terms = words(text)
    result = ['w:' + w for w in terms]
    result += ['b:' + a + ' ' + b for a, b in zip(terms, terms[1:])]
    for word in set(terms):
        if len(word) >= 4:
            padded = '^' + word + '$'
            result += ['c:' + padded[i:i+3] for i in range(len(padded)-2)]
    # Generic syntax signals are learned features, never direct routing rules.
    # Existing vocabularies have no such columns, so their transforms stay unchanged.
    if re.search(r'(?m)^\s*def\s+\w+\([^\n]*\)',text):
        result.append('structure:python_signature')
    if '\"\"\"' in text or "'''" in text:
        result.append('structure:docstring')
    if '>>>' in text:
        result.append('structure:doctest')
    if re.search(r'(?m)^\s*assert\s',text):
        result.append('structure:assertion')
    return result


class Vectorizer:
    def __init__(self, vocabulary, idf):
        self.vocabulary = vocabulary
        self.idf = np.asarray(idf, dtype=np.float32)

    @classmethod
    def fit(cls, texts, limit=4096):
        counts = {}
        for text in texts:
            for term in set(features(text)):
                counts[term] = counts.get(term, 0) + 1
        selected = sorted(counts, key=lambda term: (-counts[term], term))[:limit]
        vocabulary = {term: i for i, term in enumerate(selected)}
        idf = [np.log((1+len(texts)) / (1+counts[term])) + 1 for term in selected]
        return cls(vocabulary, idf)

    def transform(self, texts):
        output = np.zeros((len(texts), len(self.vocabulary)), dtype=np.float32)
        for row, text in enumerate(texts):
            for term in features(text):
                col = self.vocabulary.get(term)
                if col is not None:
                    output[row, col] += .3 if term.startswith('c:') else 1.0
        output = np.log1p(output) * self.idf
        output /= np.maximum(np.linalg.norm(output, axis=1, keepdims=True), 1e-8)
        return output


def sigmoid(value):
    return 1 / (1 + np.exp(-np.clip(value, -30, 30)))


def softmax(value):
    value = value - value.max(axis=1, keepdims=True)
    exp = np.exp(value)
    return exp / exp.sum(axis=1, keepdims=True)


def is_coding_spec(text):
    return bool(re.search(r'(?m)^\s*def\s+\w+\([^\n]*\)',text)) and ('\"\"\"' in text or "'''" in text)


def coding_document(text):
    match=re.search(r'([\'\"]{3})(.*?)\1',text,re.S)
    return match.group(2).strip() if match else text


class DecisionModel:
    def __init__(self, metadata, arrays):
        self.metadata = metadata
        self.arrays = arrays
        self.vectorizer = Vectorizer(metadata['vocabulary'], arrays['idf'])
        self.calibration = None

    @classmethod
    def load(cls, directory):
        directory = Path(directory)
        metadata = json.loads((directory / 'model.json').read_text(encoding='utf-8'))
        weights = directory / 'weights.npz'
        if hashlib.sha256(weights.read_bytes()).hexdigest() != metadata['weights_sha256']:
            raise ValueError('Tavi weight checksum mismatch')
        with np.load(weights, allow_pickle=False) as source:
            arrays = {key: source[key] for key in source.files}
        if not all(np.isfinite(a).all() for a in arrays.values()):
            raise ValueError('Tavi weights contain invalid numeric values')
        doc=metadata.get('coding_doc_adapter')
        if doc is not None:
            try:
                size=len(doc['vocabulary']);width=doc['width'];gate=doc['minimum_confidence']
                valid=(type(width) is int and 1<=width<=256 and type(gate) in (int,float) and .5<=gate<1 and
                       doc['architecture']=='docstring_tfidf_mlp' and
                       sorted(doc['vocabulary'].values())==list(range(size)) and
                       arrays['coding_doc_idf'].shape==(size,) and arrays['coding_doc_W'].shape==(size,width) and
                       arrays['coding_doc_b'].shape==(width,) and arrays['coding_doc_V'].shape==(width,4) and arrays['coding_doc_c'].shape==(4,))
                if doc.get('review_gate') is not None:
                    gate=doc['review_gate']['threshold']
                    valid &= (type(gate) in (int,float) and 0<gate<1 and arrays['coding_doc_review_W'].shape==(size,) and arrays['coding_doc_review_b'].shape==())
            except (KeyError,TypeError):valid=False
            if not valid:raise ValueError('Invalid coding document adapter')
        presence=metadata.get('skill_presence')
        if presence is not None:
            try:
                size=len(presence['vocabulary']);gate=presence['threshold']
                valid=(type(gate) in (int,float) and 0<gate<1 and sorted(presence['vocabulary'].values())==list(range(size)) and
                       arrays['skill_presence_idf'].shape==(size,) and arrays['skill_presence_W'].shape==(size,) and arrays['skill_presence_b'].shape==())
            except (KeyError,TypeError):valid=False
            if not valid:raise ValueError('Invalid skill presence gate')
        if metadata.get('format') == 'tavi-neural-int8-v1':
            from tavi_quantize import QuantizedDecisionModel
            model = QuantizedDecisionModel(metadata, arrays)
        else:
            model = cls(metadata, arrays)
        probability_path = directory/'probability.json'
        if probability_path.is_file():
            from tavi_probability import validate_calibration
            calibration = json.loads(probability_path.read_text(encoding='utf-8'))
            validate_calibration(calibration, metadata)
            model.calibration = calibration
        return model

    def predict(self, texts):
        x = self.vectorizer.transform(texts)
        a = self.arrays
        hidden = np.tanh(x @ a['W'] + a['b'])
        tier = softmax((hidden @ a['Wt'] + a['bt']) / self.metadata.get('temperature', 1))
        adapter = self.metadata.get('tier_adapter')
        if adapter:
            av = Vectorizer(adapter['vocabulary'], a['tier_adapter_idf'])
            adjusted = softmax(np.log(np.maximum(tier, 1e-12))+av.transform(texts) @ a['tier_adapter_W']+a['tier_adapter_b'])
            apply=adjusted.max(axis=1)>=adapter.get('minimum_confidence',0)
            if adapter.get('preserve_base_recommendations'):
                apply &= ~((adjusted.argmax(1)==3)&(tier.argmax(1)!=3)&(tier.max(1)>=.5))
            if adapter.get('preserve_structured_specs'):
                structured=np.array([bool(re.search(r'(?m)^def\s+\w+\([^\n]*\).*:', text)) for text in texts])
                apply &= ~(structured&(adjusted.argmax(1)==3)&(tier.argmax(1)!=3)&(tier.max(1)>=.5))
            tier = np.where(apply[:,None],adjusted,tier)
        coding=self.metadata.get('coding_adapter')
        if coding:
            cv=Vectorizer(coding['vocabulary'],a['coding_adapter_idf'])
            adjusted=softmax(np.log(np.maximum(tier,1e-12))+cv.transform(texts) @ a['coding_adapter_W']+a['coding_adapter_b'])
            apply=np.array([is_coding_spec(text) for text in texts])&(adjusted.max(1)>=coding['minimum_confidence'])
            # Preserve a previously routable specification if the new head abstains.
            apply &= ~((adjusted.argmax(1)==3)&(tier.argmax(1)!=3)&(tier.max(1)>=.5))
            tier=np.where(apply[:,None],adjusted,tier)
        document=self.metadata.get('coding_doc_adapter')
        if document:
            indices=np.array([i for i,text in enumerate(texts) if is_coding_spec(text)],dtype=int)
            if len(indices):
                dv=Vectorizer(document['vocabulary'],a['coding_doc_idf'])
                dx=dv.transform([coding_document(texts[i]) for i in indices])
                dh=np.tanh(dx@a['coding_doc_W']+a['coding_doc_b'])
                adjusted=softmax(dh@a['coding_doc_V']+a['coding_doc_c'])
                apply=adjusted.max(1)>=document['minimum_confidence']
                expert=document.get('review_gate')
                if expert:
                    review=sigmoid(dx@a['coding_doc_review_W']+a['coding_doc_review_b'])
                    apply &= (adjusted.argmax(1)!=3)|(review>=expert['threshold'])
                else:
                    # Legacy optional adapters preserve previously routable input.
                    apply &= ~((adjusted.argmax(1)==3)&(tier[indices].argmax(1)!=3)&(tier[indices].max(1)>=.5))
                tier[indices]=np.where(apply[:,None],adjusted,tier[indices])
        skills = sigmoid(hidden @ a['Ws'] + a['bs'])
        extensions = self.metadata.get('extensions', [self.metadata['extension']] if self.metadata.get('extension') else [])
        for extension in extensions:
            key = extension.get('array_prefix', 'extension')
            ev = Vectorizer(extension['vocabulary'], a[key+'_idf'])
            raw = sigmoid(ev.transform(texts) @ a[key+'_W'] + a[key+'_b'])
            threshold = np.array(extension['thresholds'],dtype='float32')
            base_threshold = self.metadata['skill_threshold']
            # Put new scores on the existing selection scale; these are scores, not calibrated probabilities.
            scaled = np.where(raw <= threshold, base_threshold*raw/np.maximum(threshold,1e-8),
                              base_threshold+(1-base_threshold)*(raw-threshold)/np.maximum(1-threshold,1e-8))
            scaled = np.where(threshold >= 1,0.,scaled)
            skills = np.concatenate((skills,scaled),axis=1)
        presence=self.metadata.get('skill_presence')
        if presence:
            pv=Vectorizer(presence['vocabulary'],a['skill_presence_idf'])
            needed=sigmoid(pv.transform(texts)@a['skill_presence_W']+a['skill_presence_b'])>=presence['threshold']
            skills=np.where(needed[:,None],skills,0.)
        external = sigmoid(hidden @ a['Wd'] + a['bd'])[:, 0]
        return tier, skills, external

    def infer(self, prompt):
        tier, skill_scores, external = self.predict([prompt])
        order = np.argsort(-skill_scores[0])
        ranked = [dict(name=self.metadata['skills'][int(i)], score=float(skill_scores[0, i])) for i in order]
        recognised = sum('w:' + w in self.vectorizer.vocabulary for w in words(prompt))
        if self.metadata.get('tier_adapter'):
            vocabulary = self.metadata['tier_adapter']['vocabulary']
            recognised = sum('w:'+w in self.vectorizer.vocabulary or 'w:'+w in vocabulary for w in words(prompt))
        if self.metadata.get('coding_adapter') and is_coding_spec(prompt):
            vocabularies=[self.vectorizer.vocabulary,self.metadata.get('tier_adapter',{}).get('vocabulary',{}),self.metadata['coding_adapter']['vocabulary']]
            recognised=sum(any('w:'+w in v for v in vocabularies) for w in words(prompt))
        if self.metadata.get('coding_doc_adapter') and is_coding_spec(prompt):
            vocabularies=[self.vectorizer.vocabulary,self.metadata.get('tier_adapter',{}).get('vocabulary',{}),self.metadata.get('coding_adapter',{}).get('vocabulary',{}),self.metadata['coding_doc_adapter']['vocabulary']]
            recognised=sum(any('w:'+w in v for v in vocabularies) for w in words(prompt))
        coverage = recognised / max(1, len(words(prompt)))
        result = dict(tier=TIERS[int(tier[0].argmax())], tier_scores=dict(zip(TIERS, map(float, tier[0]))),
                    skills=ranked, external_score=float(external[0]), vocabulary_coverage=coverage,
                    skill_threshold=self.metadata['skill_threshold'], external_threshold=self.metadata['external_threshold'])
        from tavi_probability import summarize
        result['probabilities'] = summarize(result, self.calibration,'python_spec' if is_coding_spec(prompt) else 'plain_text')
        return result


def train(rows, skill_names, directory, epochs=240, seed=20261028):
    """Fit only training rows; validation selects thresholds/temperature, not weights."""
    training = [r for r in rows if r['split'] == 'train']
    validation = [r for r in rows if r['split'] == 'validation']
    vectorizer = Vectorizer.fit([r['prompt'] for r in training])
    x = vectorizer.transform([r['prompt'] for r in training])
    rng = np.random.default_rng(seed)
    size, dimensions = x.shape
    hidden_size = 96
    a = dict(W=rng.normal(0, .12, (dimensions, hidden_size)).astype('float32'),
             b=np.zeros(hidden_size, dtype='float32'),
             Wt=rng.normal(0, .1, (hidden_size, 4)).astype('float32'), bt=np.zeros(4, dtype='float32'),
             Ws=rng.normal(0, .1, (hidden_size, len(skill_names))).astype('float32'), bs=np.full(len(skill_names), -2, dtype='float32'),
             Wd=rng.normal(0, .1, (hidden_size, 1)).astype('float32'), bd=np.zeros(1, dtype='float32'))
    skill_map = {name: i for i, name in enumerate(skill_names)}
    yt = np.zeros((size, 4), dtype='float32')
    ys = np.zeros((size, len(skill_names)), dtype='float32')
    yd = np.array([[r['external']] for r in training], dtype='float32')
    tier_mask = np.array([[r['tier'] is not None] for r in training], dtype='float32')
    for i, row in enumerate(training):
        if row['tier'] is not None:
            yt[i, TIERS.index(row['tier'])] = 1
        for name in row['skills']:
            ys[i, skill_map[name]] = 1
    pos = np.minimum(30, (size - ys.sum(axis=0)) / np.maximum(ys.sum(axis=0), 1))
    skill_weights = np.where(ys > .5, pos, 1)
    discovery_weights = np.where(yd > .5, min(15, size / max(yd.sum(), 1)), 1)
    tier_weights = np.sqrt(tier_mask.sum() / np.maximum(yt.sum(axis=0), 1))
    tw = (yt * tier_weights).sum(axis=1, keepdims=True) * tier_mask
    moment = {k: np.zeros_like(v) for k, v in a.items()}
    velocity = {k: np.zeros_like(v) for k, v in a.items()}
    losses = []
    for epoch in range(1, epochs+1):
        hidden = np.tanh(x @ a['W'] + a['b'])
        pt = softmax(hidden @ a['Wt'] + a['bt'])
        ps = sigmoid(hidden @ a['Ws'] + a['bs'])
        pd = sigmoid(hidden @ a['Wd'] + a['bd'])
        dt = (pt - yt) * tw / max(tw.sum(), 1)
        ds = 2 * (ps - ys) * skill_weights / (size * len(skill_names))
        dd = .6 * (pd - yd) * discovery_weights / size
        dh = (dt @ a['Wt'].T + ds @ a['Ws'].T + dd @ a['Wd'].T) * (1-hidden**2)
        grads = dict(W=x.T @ dh, b=dh.sum(axis=0), Wt=hidden.T @ dt, bt=dt.sum(axis=0),
                     Ws=hidden.T @ ds, bs=ds.sum(axis=0), Wd=hidden.T @ dd, bd=dd.sum(axis=0))
        for key in a:
            grad = grads[key] + (.0001*a[key] if key.startswith('W') else 0)
            moment[key] = .9*moment[key] + .1*grad
            velocity[key] = .999*velocity[key] + .001*grad**2
            a[key] -= .012 * (moment[key]/(1-.9**epoch)) / (np.sqrt(velocity[key]/(1-.999**epoch))+1e-8)
        if epoch == 1 or epoch % 40 == 0 or epoch == epochs:
            tier_loss = float((-yt*np.log(pt+1e-7)*tw).sum()/max(tw.sum(), 1))
            skill_loss = float((-skill_weights*(ys*np.log(ps+1e-7)+(1-ys)*np.log(1-ps+1e-7))).mean())
            losses.append(dict(epoch=epoch, tier_loss=tier_loss, skill_loss=skill_loss))
            print(json.dumps(losses[-1]), flush=True)
    metadata = dict(format='tavi-neural-v1', skills=skill_names, vocabulary=vectorizer.vocabulary,
                    skill_threshold=.5, external_threshold=.5, temperature=1, seed=seed,
                    architecture='TF-IDF words/bigrams/character-trigrams -> tanh96 -> tier4/skills/discovery',
                    training_rows=len(training), validation_rows=len(validation), epochs=epochs,
                    origin='Original synthetic policy examples plus weak skill-metadata positives; no real outcome labels')
    a['idf'] = vectorizer.idf
    model = DecisionModel(metadata, a)
    if validation:
        # Threshold selection and temperature use validation only, never heldout cases.
        vt, vs, vd = model.predict([r['prompt'] for r in validation])
        vtruth = np.zeros_like(vs)
        for i, row in enumerate(validation):
            for name in row['skills']:
                vtruth[i, skill_map[name]] = 1
        trials = []
        for threshold in np.arange(.1, .91, .05):
            predicted = vs >= threshold
            tp = (predicted * vtruth).sum()
            f1 = 2*tp / max(predicted.sum()+vtruth.sum(), 1)
            trials.append((float(f1), float(threshold)))
        metadata['skill_threshold'] = max(trials)[1]
        metadata['validation_skill_f1'] = max(trials)[0]
        dtruth = np.array([r['external'] for r in validation])
        metadata['external_threshold'] = max((float(((vd >= t) == dtruth).mean()), float(t)) for t in np.arange(.2, .81, .05))[1]
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(directory/'weights.npz', **a)
    metadata['weights_sha256'] = hashlib.sha256((directory/'weights.npz').read_bytes()).hexdigest()
    metadata['parameters'] = sum(v.size for k, v in a.items() if k != 'idf')
    (directory/'model.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    return model, losses
