"""Reproducible, isolated larger-model candidate tests (no network or activation)."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import numpy as np

from tavi_health import activate_candidate
from tavi_model import DecisionModel, train

ROWS = [
    dict(id='a', prompt='Make a navigation menu responsive on mobile', tier='balanced', skills=['ui'], external=False, split='train'),
    dict(id='b', prompt='Explain this small Python function', tier='fast', skills=[], external=False, split='train'),
    dict(id='c', prompt='Research new cybersecurity controls for websites', tier='deep', skills=['security'], external=True, split='train'),
    dict(id='d', prompt='Write tests for website account login', tier='balanced', skills=['security'], external=False, split='train'),
]
SKILLS = ['security', 'ui']


class CapacityExperimentTests(unittest.TestCase):
    def test_wider_candidate_has_more_real_trainable_weights_and_loads(self):
        with tempfile.TemporaryDirectory() as root:
            base_path = Path(root) / 'baseline'
            wide_path = Path(root) / 'candidate'
            base, _ = train(ROWS, SKILLS, base_path, epochs=3)
            wide, _ = train(ROWS, SKILLS, wide_path, epochs=3, hidden_size=256, vocab_limit=8192)
            self.assertFalse(base.metadata['experimental_capacity'])
            self.assertTrue(wide.metadata['experimental_capacity'])
            self.assertEqual(wide.arrays['W'].shape[1], 256)
            self.assertGreater(wide.metadata['parameters'], base.metadata['parameters'] * 2)
            loaded = DecisionModel.load(wide_path)
            self.assertEqual(loaded.metadata['parameters'], wide.metadata['parameters'])
            prediction = loaded.infer('Fix navigation for phone layouts')
            self.assertIn(prediction['tier'], ('fast', 'balanced', 'deep', 'review'))
            self.assertTrue(np.isfinite(list(prediction['tier_scores'].values())).all())

    def test_historical_defaults_are_reproducible(self):
        with tempfile.TemporaryDirectory() as root:
            a, _ = train(ROWS, SKILLS, Path(root) / 'default', epochs=2)
            b, _ = train(ROWS, SKILLS, Path(root) / 'explicit', epochs=2,
                         hidden_size=96, vocab_limit=4096, seed=20261028)
            for key in ('W', 'b', 'Wt', 'bt', 'Ws', 'bs', 'Wd', 'bd', 'idf'):
                np.testing.assert_array_equal(a.arrays[key], b.arrays[key])
            self.assertEqual(a.metadata['architecture'], b.metadata['architecture'])

    def test_invalid_configs_do_not_train(self):
        with tempfile.TemporaryDirectory() as root:
            for kw in ({'hidden_size': 12}, {'hidden_size': True}, {'hidden_size': 4096},
                       {'vocab_limit': 64000}, {'vocab_limit': 1025}, {'seed': -1}):
                with self.subTest(kw=kw), self.assertRaises(ValueError):
                    train(ROWS, SKILLS, Path(root) / 'never_created', epochs=1, **kw)

    def test_experiment_cannot_be_activated_even_with_passed_report(self):
        fake = SimpleNamespace(metadata={'experimental_capacity': True})
        with tempfile.TemporaryDirectory() as root:
            with patch('tavi_model.DecisionModel.load', return_value=fake):
                with self.assertRaisesRegex(ValueError, 'cannot be activated'):
                    activate_candidate(Path(root) / 'config.json', b'{}',
                                       Path(root) / 'candidate', {'passed': True})


if __name__ == '__main__':
    unittest.main()
