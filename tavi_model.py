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


class DecisionModel:
    def __init__(self, metadata, arrays):
        self.metadata = metadata
        self.arrays = arrays
        self.vectorizer = Vectorizer(metadata['vocabulary'], arrays['idf'])

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
        return cls(metadata, arrays)

    def predict(self, texts):
        x = self.vectorizer.transform(texts)
        a = self.arrays
        hidden = np.tanh(x @ a['W'] + a['b'])
        tier = softmax((hidden @ a['Wt'] + a['bt']) / self.metadata.get('temperature', 1))
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
        external = sigmoid(hidden @ a['Wd'] + a['bd'])[:, 0]
        return tier, skills, external

    def infer(self, prompt):
        tier, skill_scores, external = self.predict([prompt])
        order = np.argsort(-skill_scores[0])
        ranked = [dict(name=self.metadata['skills'][int(i)], score=float(skill_scores[0, i])) for i in order]
        recognised = sum('w:' + w in self.vectorizer.vocabulary for w in words(prompt))
        coverage = recognised / max(1, len(words(prompt)))
        return dict(tier=TIERS[int(tier[0].argmax())], tier_scores=dict(zip(TIERS, map(float, tier[0]))),
                    skills=ranked, external_score=float(external[0]), vocabulary_coverage=coverage,
                    skill_threshold=self.metadata['skill_threshold'], external_threshold=self.metadata['external_threshold'])


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
