"""Regression coverage for numeric-only computer-use telemetry."""
from datetime import datetime, timezone
import io
import json
import unittest

from tavi_metrics import UsageMetrics
from tavi_observe import dispatch
from tavi_observe_stream import run


def _snapshot(controls=None):
    return dict(format='tavi-control-snapshot-v1',
                source='supported_browser_dom',
                snapshot_id='metric-test-1',
                captured_at=datetime.now(timezone.utc).isoformat(),
                viewport=[800,600],
                controls=controls if controls is not None else [
                    dict(id='g',role='button',label='Go',context='',
                         visible=True,enabled=True,bounds=[20,30,100,50])])


class MetricsTests(unittest.TestCase):
    def test_dom_only_is_measured_with_no_image_or_secret_content(self):
        secret='private-user-value-do-not-log'
        metrics=UsageMetrics()
        state=_snapshot()
        state['controls'][0]['context']=secret
        query=[dict(id='request-1',task='Press Go with '+secret,target='Go')]
        packet=dispatch(state,query,metrics=metrics)
        self.assertEqual(packet['counts']['ocr_passes'],0)
        metrics.observe(packet,wire_bytes=567)
        report=metrics.summary()
        serialized=json.dumps(report)
        self.assertNotIn(secret,serialized)
        self.assertNotIn('request-1',serialized)
        self.assertNotIn('metric-test-1',serialized)
        self.assertEqual(report['counters']['observations'],1)
        self.assertEqual(report['counters']['queries'],1)
        self.assertEqual(report['counters']['response_bytes_total'],567)
        self.assertEqual(report['counters']['routes_host_control'],1)
        self.assertIn('dom_resolve',report['timings'])
        self.assertNotIn('visual_fallback',report['timings'])
        self.assertEqual(report['provider_tokens']['status'],'unavailable')
        self.assertIsNone(report['provider_tokens']['input'])
        self.assertFalse(report['actual_model_tokens_measured'])

    def test_provider_counting_only_explicit_host_usage(self):
        m=UsageMetrics()
        m.provider_usage()
        missing=m.summary()
        self.assertEqual(missing['provider_tokens']['unmeasured_calls'],1)
        self.assertIsNone(missing['provider_tokens']['output'])
        m.provider_usage(input_tokens=100,output_tokens=20,cached_input_tokens=50,
                         elapsed_ms=14.9)
        report=m.summary()
        self.assertEqual(report['provider_tokens']['status'],'partial')
        self.assertEqual(report['provider_tokens']['input'],100)
        self.assertEqual(report['provider_tokens']['output'],20)
        self.assertEqual(report['provider_tokens']['cached_input'],50)
        self.assertEqual(report['provider_tokens']['measured_calls'],1)
        self.assertTrue(report['actual_model_tokens_measured'])
        self.assertIn('host_model',report['timings'])

    def test_bad_usage_does_not_mutate_counters(self):
        m=UsageMetrics()
        before=m.summary()
        bad=[
            dict(input_tokens=-1,output_tokens=2),
            dict(input_tokens=3,output_tokens=4,cached_input_tokens=4),
            dict(input_tokens=1,output_tokens=None),
            dict(input_tokens=True,output_tokens=1),
            dict(elapsed_ms=float('nan')),
        ]
        for params in bad:
            with self.subTest(params=params),self.assertRaises(ValueError):
                m.provider_usage(**params)
        self.assertEqual(m.summary(),before)

    def test_bounded_samples_and_nearest_rank_p95(self):
        m=UsageMetrics(sample_limit=16)
        for x in range(20):
            m.record_stage('host_recheck',x)
        stats=m.summary()['timings']['host_recheck']
        self.assertEqual(stats['count'],20)
        self.assertEqual(stats['samples_kept'],16)
        self.assertEqual(stats['median_ms'],11.5)
        self.assertEqual(stats['p95_ms'],19)
        self.assertEqual(stats['max_ms'],19)
        with self.assertRaises(ValueError):
            m.record_stage('arbitrary_control_name',1)
        with self.assertRaises(ValueError):
            m.record_stage('action',float('inf'))

    def test_host_browser_timing_integration_uses_no_metadata(self):
        from tavi_browser_snapshot import capture_controls
        class Page:
            def evaluate(self, _):
                return dict(viewport=[800,600],controls=[
                    dict(id='button1',label='Go',role='button',visible=True,
                         enabled=True,bounds=[20,20,90,45])])
        m=UsageMetrics()
        capture_controls(Page(),metrics=m)
        self.assertIn('browser_dom_capture',m.summary()['timings'])
        self.assertEqual(m.summary()['counters'],{})

    def test_stream_opt_in_telemetry_contains_numeric_only_summary(self):
        state=_snapshot()
        request=dict(id='metrics-test',snapshot=state,
                     queries=[dict(task='Inspect Go',target='Go')])
        output=io.StringIO()
        m=UsageMetrics()
        self.assertEqual(run(io.StringIO(json.dumps(request)+'\n'),output,
                             metrics=m,session_factory=lambda:None),0)
        records=[json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(records[1]['status'],'routed')
        telemetry=records[1]['telemetry']
        self.assertEqual(telemetry['counters']['observations'],1)
        self.assertGreater(telemetry['counters']['response_bytes_total'],0)
        self.assertEqual(telemetry['provider_tokens']['status'],'unavailable')
        self.assertIn('stream_request',telemetry['timings'])
        output=io.StringIO()
        self.assertEqual(run(io.StringIO(json.dumps(request)+'\n'),output,
                             session_factory=lambda:None),0)
        self.assertNotIn('telemetry',json.loads(output.getvalue().splitlines()[1]))

    def test_invalid_route_packet_rejected_before_persisting(self):
        metrics=UsageMetrics()
        packet=dispatch(_snapshot(),[dict(task='Inspect Go',target='Go')])
        for altered in [dict(packet,executed_actions=True),
                        dict(packet,counts=dict(packet['counts'],ocr_passes=2)),
                        dict(packet,routes=[dict(packet['routes'][0],route='click')])]:
            with self.assertRaises(ValueError):
                metrics.observe(altered)
        self.assertEqual(metrics.summary()['counters'],{})

    def test_invalid_sample_limit(self):
        for value in (0,15,100001,True,'512'):
            with self.assertRaises(ValueError):
                UsageMetrics(sample_limit=value)


if __name__=='__main__':
    unittest.main()
