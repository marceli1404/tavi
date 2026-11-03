"""Trust and comparability regressions for the fixed matched browser benchmark."""
import unittest
from benchmarks.matched_browser_workflows import (
    TASKS, MODES, fixture, is_fixture, run, summarize, wilson, percentile)


class MatchedBrowserProtocolTests(unittest.TestCase):
    def test_only_pre_registered_non_sensitive_workflows(self):
        self.assertEqual(len(TASKS),4)
        for name,labels in TASKS.items():
            self.assertEqual(len(labels),3)
            self.assertEqual(len(set(labels)),3)
            self.assertIn('data-tavi-matched-fixture="v1"',fixture(labels))
            self.assertNotIn('https://',fixture(labels))
            self.assertNotIn('http://',fixture(labels))
        with self.assertRaises(ValueError):
            fixture(('Buy', 'Pay', 'Transfer'))
        with self.assertRaises(ValueError):
            fixture(('Begin', 'Unknown', 'Finish'))

    def test_exactly_two_strategies_and_same_host_action(self):
        self.assertEqual(MODES,('screenshot_ocr','tavi_dom'))

    def test_invalid_repetition_count_is_rejected_before_browser_launch(self):
        for count in (0,11,-1,True,'4',None):
            with self.subTest(count=count),self.assertRaises(ValueError):
                run(repeats=count)

    def test_report_does_not_infer_unmeasured_tokens(self):
        records=[]
        for mode,elapsed in (('screenshot_ocr',115.0),('tavi_dom',30.0)):
            records.append(dict(workflow='onboarding',variant=mode,
                    repeat=0,success=True,completed_steps=3,
                    elapsed_ms=elapsed,error_code=None,
                    counters={'verified_steps':3,'clicks_attempted':3}))
        summary=summarize(records)
        self.assertEqual(summary['paired']['pairs'],1)
        self.assertEqual(summary['paired']['both_succeeded'],1)
        self.assertAlmostEqual(summary['paired']['median_paired_latency_ratio'],3.833)
        self.assertEqual(summary['paired']['median_paired_delta_ms'],85.0)
        self.assertIsNone(summary['paired']['provider_input_tokens'])
        self.assertIsNone(summary['paired']['provider_cost'])
        self.assertEqual(summary['paired']['hosted_model_calls'],0)

    def test_failures_are_counted_not_erased(self):
        rows=[dict(workflow='catalog',variant='screenshot_ocr',repeat=0,
                   success=False,completed_steps=0,elapsed_ms=300.0,
                   error_code='target_not_found_or_ambiguous',counters={'screenshots':1}),
              dict(workflow='catalog',variant='tavi_dom',repeat=0,
                   success=True,completed_steps=3,elapsed_ms=25.0,
                   error_code=None,counters={'dom_captures':6})]
        result=summarize(rows)
        self.assertEqual(result['screenshot_ocr']['success_rate'],0)
        self.assertEqual(result['tavi_dom']['success_rate'],1)
        self.assertEqual(result['paired']['both_succeeded'],0)
        self.assertEqual(result['screenshot_ocr']['failure_codes'],
                         {'target_not_found_or_ambiguous':1})

    def test_confidence_and_percentiles(self):
        self.assertEqual(wilson(0,0),None)
        self.assertEqual(percentile([],0.95),None)
        self.assertEqual(percentile([4,1,3,2],.95),4)
        low,high=wilson(1,1)
        self.assertLess(low,0.3)
        self.assertEqual(high,1.0)


if __name__ == '__main__':
    unittest.main()
