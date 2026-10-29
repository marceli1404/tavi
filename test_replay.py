import copy
import unittest
from benchmarks.replay import replay


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.outcomes = {'results': [dict(task_id=t, role=r, elapsed_seconds=1,
            verdict={'passed': passed}) for t, r, passed in
            [('a', 'cheap', True), ('a', 'strong', True), ('b', 'cheap', False), ('b', 'strong', True)]]}
        self.routes = {'a': 'cheap', 'b': 'review'}

    def test_unresolved_counts_as_failure(self):
        result = replay(self.outcomes, self.routes, repetitions=100)
        self.assertEqual(result['summary']['success_rate'], .5)
        self.assertEqual(result['summary']['unresolved'], 1)
        self.assertEqual(result['static_baselines']['strong']['success_difference'], -.5)

    def test_fallback_is_measured_and_reproducible(self):
        result = replay(self.outcomes, self.routes, 'strong', 100)
        self.assertEqual(result['summary']['passed'], 2)
        self.assertEqual(result['summary']['abstained'], 1)
        self.assertEqual(result['summary']['selected_generation_seconds'], 2)
        self.assertEqual(result, replay(self.outcomes, self.routes, 'strong', 100))

    def test_invalid_matrices_and_routes_rejected(self):
        invalid = []
        duplicate = copy.deepcopy(self.outcomes)
        duplicate['results'].append(duplicate['results'][0])
        invalid.append(duplicate)
        invalid.append({'results': self.outcomes['results'][:-1]})
        for field, value in [('elapsed_seconds', float('nan')), ('verdict', {'passed': 1})]:
            data = copy.deepcopy(self.outcomes)
            data['results'][0][field] = value
            invalid.append(data)
        for data in invalid:
            with self.assertRaises(ValueError):
                replay(data, self.routes, repetitions=100)
        for routes in [{'a': 'cheap'}, {'a': 'cheap', 'b': 'unknown'}]:
            with self.assertRaises(ValueError):
                replay(self.outcomes, routes, repetitions=100)
        with self.assertRaises(ValueError):
            replay(self.outcomes, self.routes, 'missing', 100)
