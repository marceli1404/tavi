import io
import json
from pathlib import Path
import queue
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
from tavi_ocr import OcrSession
from tavi_stream import run

class FakeProcess:
    def __init__(self,lines):
        self.stdin=io.StringIO(); self.stdout=io.StringIO('\n'.join(lines)+'\n'); self.returncode=None
    def poll(self): return self.returncode
    def wait(self,timeout=None): self.returncode=0; return 0
    def kill(self): self.returncode=-1

class SessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.image=Path(self.tmp.name)/"Go 'unicode-ü'.png"; self.image.write_bytes(b'fixture')

    def session(self,responses):
        process=FakeProcess([json.dumps(r) if not isinstance(r,str) else r for r in responses])
        with patch('tavi_ocr.os',SimpleNamespace(name='nt')),patch('tavi_ocr.subprocess.Popen',return_value=process):
            session=OcrSession(timeout=.2)
        self.addCleanup(session.close)
        return session,process

    def test_reuses_one_process_with_correlated_fresh_requests(self):
        session,process=self.session([{'status':'ready','protocol':1},{'id':1,'status':'available','words':[]},{'id':2,'status':'available','words':[]}])
        session(self.image); session(self.image)
        requests=[json.loads(line) for line in process.stdin.getvalue().splitlines()]
        self.assertEqual([r['id'] for r in requests],[1,2])
        self.assertEqual(requests[0]['path'],str(self.image.resolve()))
        self.assertEqual(session.requests,2)
        session.close(); self.assertIsNotNone(process.poll())

    def test_mismatched_response_closes_session(self):
        session,process=self.session([{'status':'ready','protocol':1},{'id':99,'status':'available'}])
        with self.assertRaises(RuntimeError): session(self.image)
        self.assertTrue(session.closed); self.assertIsNotNone(process.poll())

    def test_unavailable_image_does_not_reuse_old_response(self):
        session,_=self.session([{'status':'ready','protocol':1},{'id':1,'status':'unavailable'},{'id':2,'status':'available','text':'new'}])
        self.assertEqual(session(self.image)['status'],'unavailable')
        self.assertEqual(session(self.image)['text'],'new')

    def test_dead_worker_closes_session(self):
        session,process=self.session([{'status':'ready','protocol':1}])
        with self.assertRaises(RuntimeError): session(self.image)
        self.assertTrue(session.closed); self.assertIsNotNone(process.poll())

    def test_bad_protocol_closes_session(self):
        session,_=self.session([{'status':'ready','protocol':1},'not json'])
        with self.assertRaises(RuntimeError): session(self.image)
        self.assertTrue(session.closed)

    def test_receive_timeout_is_bounded(self):
        session=OcrSession.__new__(OcrSession); session._lines=queue.Queue(); session.timeout=.001
        with self.assertRaisesRegex(RuntimeError,'timed out'): session._receive()

    def test_closed_session_rejects_further_work(self):
        session,_=self.session([{'status':'ready','protocol':1}]); session.close()
        with self.assertRaisesRegex(RuntimeError,'closed'): session(self.image)

    def test_initialization_failure_cleans_process(self):
        process=FakeProcess(['{"status":"unavailable"}'])
        with patch('tavi_ocr.os',SimpleNamespace(name='nt')),patch('tavi_ocr.subprocess.Popen',return_value=process):
            with self.assertRaises(RuntimeError): OcrSession(timeout=.2)
        self.assertIsNotNone(process.poll())

class FakeSession:
    def __init__(self): self.requests=0; self.closed=False
    def __enter__(self): return self
    def __exit__(self,*args): self.closed=True

class StreamTests(unittest.TestCase):
    def execute(self,lines):
        self.session=FakeSession(); output=io.StringIO()
        def proposal(image,task,target,**kwargs):
            self.assertFalse(kwargs.get('execute',False)); self.assertIs(kwargs['ocr_fn'],self.session)
            self.session.requests+=1
            return {'proposal_id':str(self.session.requests),'hosted_calls':0,'image_bytes_sent':0}
        with patch('tavi_stream.propose',side_effect=proposal) as call:
            run(io.StringIO(lines),output,session_factory=lambda:self.session)
        return [json.loads(line) for line in output.getvalue().splitlines()],call

    def test_multiple_requests_use_one_owned_session_and_close_at_eof(self):
        request=dict(image='a.png',task='Press Go',target='Go')
        rows,call=self.execute(json.dumps(request)+'\n'+json.dumps(dict(request,image='b.png'))+'\n')
        self.assertEqual(call.call_count,2); self.assertTrue(self.session.closed)
        self.assertEqual([r['proposal_id'] for r in rows[1:]],['1','2'])
        self.assertTrue(all(not r['proposal_reused'] for r in rows[1:]))

    def test_stream_cannot_enable_hosted_execution(self):
        rows,call=self.execute(json.dumps(dict(image='a.png',task='x',target='Go',execute=True))+'\n')
        call.assert_not_called(); self.assertEqual(rows[-1]['status'],'error')

    def test_per_request_auto_click_setting_is_not_accepted(self):
        rows,call=self.execute(json.dumps(dict(image='a.png',task='x',target='Go',auto_click=True))+'\n')
        call.assert_not_called(); self.assertEqual(rows[-1]['status'],'error')

    def test_trusted_startup_policy_reaches_proposal_without_clicking(self):
        output=io.StringIO(); session=FakeSession()
        with patch('tavi_stream.propose',return_value={'hosted_calls':0,'executed_actions':False}) as call:
            run(io.StringIO(json.dumps(dict(image='a.png',task='x',target='Go'))+'\n'),output,
                session_factory=lambda:session,auto_click=True)
        self.assertIs(call.call_args.kwargs['auto_click'],True)
        self.assertFalse(json.loads(output.getvalue().splitlines()[1])['executed_actions'])

    def test_invalid_input_does_not_execute_and_next_request_can_succeed(self):
        rows,call=self.execute('invalid json\n'+json.dumps(dict(image='a.png',task='x',target='Go'))+'\n')
        self.assertEqual(rows[1]['status'],'error'); self.assertEqual(call.call_count,1)

    def test_invalid_max_edge_is_reported(self):
        rows,call=self.execute(json.dumps(dict(image='a.png',task='x',target='Go',max_edge='1600'))+'\n')
        call.assert_not_called(); self.assertEqual(rows[-1]['status'],'error')

    def test_oversized_request_ends_session(self):
        rows,call=self.execute('x'*16385+'\n')
        call.assert_not_called(); self.assertTrue(self.session.closed)
        self.assertEqual(rows[-1]['status'],'error')
