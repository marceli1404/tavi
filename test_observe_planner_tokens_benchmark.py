"""Benchmarks must measure real tokenizer encodings, not model API billing."""
import unittest
from benchmarks.observe_planner_tokens_benchmark import benchmark,fixture,CASES


class TestPlannerTokenBenchmark(unittest.TestCase):
    def test_fixed_workloads_are_bounded(self):
        self.assertGreaterEqual(len(CASES),5)
        for name,(controls,number,variant) in CASES.items():
            with self.subTest(name=name):
                snapshot,queries=fixture(controls_count=controls,
                                         queries_count=number,variant=variant)
                self.assertLessEqual(len(snapshot['controls']),17)
                self.assertTrue(1<=len(queries)<=16)
        with self.assertRaises(ValueError):
            fixture(controls_count=10000)
        with self.assertRaises(ValueError):
            fixture(queries_count=0)

    def test_projection_preserves_route_policy_and_counts(self):
        class FakeCodepointEncoder:
            def encode(self,value):
                return list(value)
        report=benchmark(iterations=5,
                         encoders={'test_codepoints_not_actual_tokens':FakeCodepointEncoder()})
        self.assertEqual(report['hosted_model_calls'],0)
        self.assertFalse(report['actual_provider_usage_measured'])
        self.assertTrue(report['correctness_verified'])
        for case in report['cases']:
            with self.subTest(case=case['case']):
                self.assertTrue(all(case['parity'].values()))
                self.assertGreater(case['full_bytes'],case['planner_bytes'])
                self.assertGreater(case['tokenizer_tokens']['test_codepoints_not_actual_tokens']['saved'],0)
                self.assertGreaterEqual(case['projection_encode_median_ms'],0)

    def test_invalid_iterations_are_rejected(self):
        for value in (0,4,1001,-5,True,'60'):
            with self.subTest(value=value),self.assertRaises(ValueError):
                benchmark(iterations=value,encoders={'irrelevant':object()})


if __name__=='__main__':
    unittest.main()
