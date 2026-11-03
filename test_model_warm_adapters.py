"""Guard warm feature reuse without changing trained routing weights."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np
from tavi_health import bundled_model
from tavi_model import DecisionModel, Vectorizer

BASE = Path(__file__).resolve().parent
PROMPTS = ['Fix a mobile navigation layout',
           'Review this SQL database',
           'def add(a, b):\n    """Sum the arguments."""\n    return a+b']


class PreparedVectorizerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = DecisionModel.load(bundled_model(BASE))

    def test_all_prepared_transforms_equal_fresh_vectorizers(self):
        model = self.model
        pairs = []
        for key, adapter, suffix in (
            ('tier', model.metadata.get('tier_adapter'), 'tier_adapter_idf'),
            ('coding', model.metadata.get('coding_adapter'), 'coding_adapter_idf'),
            ('coding_doc', model.metadata.get('coding_doc_adapter'), 'coding_doc_idf'),
            ('presence', model.metadata.get('skill_presence'), 'skill_presence_idf'),
        ):
            if adapter is not None:
                pairs.append((getattr(model, '_'+key+'_vectorizer'),
                              adapter['vocabulary'], model.arrays[suffix]))
        pairs.extend((vectorizer, ext['vocabulary'],
                      model.arrays[ext.get('array_prefix','extension')+'_idf'])
                     for ext,vectorizer in model._extension_vectorizers)
        self.assertGreater(len(pairs), 0)
        for prepared, vocabulary, idf in pairs:
            self.assertIsInstance(prepared, Vectorizer)
            for prompt in PROMPTS:
                expected = Vectorizer(vocabulary, idf).transform([prompt])
                np.testing.assert_array_equal(prepared.transform([prompt]), expected)

    def test_model_inference_does_not_rebuild_feature_mappings(self):
        model = self.model
        initial = model.infer(PROMPTS[0])
        with patch('tavi_model.Vectorizer', side_effect=AssertionError('Rebuilt vectorizer')):
            again = model.infer(PROMPTS[0])
            other = model.infer(PROMPTS[1])
        self.assertEqual(initial, again)
        self.assertIn(other['tier'], ('fast','balanced','deep','review'))

    def test_optional_int8_model_reuses_extension_mappings(self):
        from tavi_quantize import QuantizedDecisionModel
        model = DecisionModel.load(BASE/'models/tavi-int8-experiment-v2')
        self.assertIsInstance(model, QuantizedDecisionModel)
        first = model.infer(PROMPTS[0])
        with patch('tavi_quantize.Vectorizer', side_effect=AssertionError('Rebuilt INT8 vectorizer')):
            second = model.infer(PROMPTS[0])
        self.assertEqual(first, second)

    def test_weights_and_model_artifact_remain_unmodified(self):
        model = self.model
        expected = model.metadata['weights_sha256']
        vectors = [model._tier_vectorizer, model._coding_vectorizer,
                   model._coding_doc_vectorizer, model._presence_vectorizer]
        for prompt in PROMPTS * 3:
            model.infer(prompt)
        self.assertEqual(expected, model.metadata['weights_sha256'])
        self.assertEqual(vectors, [model._tier_vectorizer, model._coding_vectorizer,
                                   model._coding_doc_vectorizer, model._presence_vectorizer])


if __name__ == '__main__':
    unittest.main()
