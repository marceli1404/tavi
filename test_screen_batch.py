"""Batch screenshot proposals share one observation without authorizing actions."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from PIL import Image, ImageDraw
import tavi_compact as compact
import tavi_stream


class ScreenshotBatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.image=Path(self.tmp.name)/'screen.png'
        im=Image.new('RGB',(1200,700),'white')
        draw=ImageDraw.Draw(im)
        draw.rectangle((30,60,250,120), fill='#252525')
        draw.rectangle((340,60,550,120), fill='#252525')
        im.save(self.image)
        im.close()
        self.words=[dict(text='Go',x=60,y=75,width=55,height=32),
                    dict(text='Stop',x=370,y=75,width=80,height=32),
                    dict(text='Toolbar',x=40,y=200,width=100,height=28)]
        self.ocr=Mock(side_effect=lambda path:dict(status='available',words=list(self.words)))
        self.queries=[dict(id='go',task='Press Go',target='Go'),
                      dict(id='stop',task='Press Stop',target='Stop'),
                      dict(id='missing',task='Find Missing',target='Missing')]

    def test_batch_matches_single_target_decisions_from_same_pixels(self):
        import tavi_target
        with patch.object(compact,'prepare',wraps=compact.prepare) as prepare, \
             patch.object(compact,'load_target',wraps=compact.load_target) as target_load:
            batch=compact.propose_batch(self.image,self.queries,ocr_fn=self.ocr)
        self.assertEqual(prepare.call_count,1)
        self.assertEqual(target_load.call_count,1)
        self.assertEqual(self.ocr.call_count,1)
        self.assertEqual(batch['image_preparations'],1)
        self.assertEqual(batch['ocr_passes'],1)
        self.assertEqual(batch['hosted_calls'],0)
        self.assertEqual(batch['image_sha256'],hashlib.sha256(self.image.read_bytes()).hexdigest())
        self.assertFalse(batch['action_sequence_authorized'])
        self.assertFalse(batch['authorization_granted'])
        self.assertFalse(batch['executed_actions'])
        self.assertTrue(batch['requires_live_host_check'])
        self.assertEqual(len(batch['proposals']),3)
        ids=set()
        for query,result in zip(self.queries,batch['proposals']):
            single=compact.propose(self.image,query['task'],query['target'],
                                   ocr_fn=lambda path:dict(status='available',words=list(self.words)))
            for key in ('status','eligible_compact_review','review_reasons',
                        'image_sha256','confidence','image','model_evidence',
                        'coordinate_space','text_packet_bytes','hosted_calls',
                        'image_bytes_sent','executed_actions','auto_click'):
                self.assertEqual(result[key],single[key],key)
            packet=result['review_packet'];baseline=single['review_packet']
            for key in ('question','task','requested_label','proposed',
                        'alternatives','confidence_scope'):
                self.assertEqual(packet[key],baseline[key],key)
            self.assertEqual(result['query_id'],query['id'])
            self.assertFalse(result['auto_click']['candidate_eligible'])
            self.assertNotIn(result['proposal_id'],ids)
            ids.add(result['proposal_id'])

    def test_unknown_duplicate_and_oversized_queries_rejected_before_ocr(self):
        invalid=[[],self.queries*6,
                 [dict(self.queries[0],id='same'),dict(self.queries[1],id='same')],
                 [dict(self.queries[0],execute=True)],
                 [dict(self.queries[0],task='')],
                 [dict(self.queries[0],target='x'*81)],
                 [dict(self.queries[0],id=3)],
                 ['Go']]
        for queries in invalid:
            with self.subTest(queries=str(queries)[:80]):
                with self.assertRaises(ValueError):
                    compact.propose_batch(self.image,queries,ocr_fn=self.ocr)
        self.ocr.assert_not_called()

    def test_source_mutation_discards_entire_batch(self):
        original=self.image.read_bytes()
        def change(path):
            self.image.write_bytes(b'replaced')
            return dict(status='available',words=list(self.words))
        with self.assertRaisesRegex(RuntimeError,'discard proposal batch'):
            compact.propose_batch(self.image,self.queries,ocr_fn=change)
        self.assertNotEqual(self.image.read_bytes(),original)

    def test_batch_does_not_share_mutable_review_packets(self):
        batch=compact.propose_batch(self.image,self.queries,ocr_fn=self.ocr)
        one,two=batch['proposals'][:2]
        self.assertNotEqual(one['proposal_id'],two['proposal_id'])
        self.assertIsNot(one['image'],two['image'])
        one['image']['prepared_size'][0]=999
        self.assertNotEqual(two['image']['prepared_size'][0],999)
        self.assertIsNot(one['review_packet'],two['review_packet'])

    def test_stream_batch_mode_never_uses_auto_click_or_hosted_review(self):
        class Session:
            requests=0
            closed=False
            def __enter__(self):return self
            def __exit__(self,*exc):self.closed=True
        session=Session()
        def fake_batch(image,queries,**options):
            self.assertIs(options['ocr_fn'],session)
            self.assertNotIn('auto_click',options)
            self.assertNotIn('execute',options)
            session.requests+=1
            return dict(format='tavi-screenshot-target-batch-v1',
                        authorization_granted=False,executed_actions=False,
                        image_preparations=1,ocr_passes=1,proposals=[])
        lines=[
            dict(id='one',image=str(self.image),targets=self.queries),
            dict(id='bad',image=str(self.image),task='Go',target='Go',targets=self.queries),
            dict(id='bad2',image=str(self.image),targets=self.queries,execute=True),
        ]
        output=io.StringIO()
        with patch.object(tavi_stream,'propose_batch',side_effect=fake_batch) as batched, \
             patch.object(tavi_stream,'propose',side_effect=AssertionError('Single path called')):
            self.assertEqual(tavi_stream.run(io.StringIO(''.join(json.dumps(x)+'\n' for x in lines)),
                                             output,session_factory=lambda:session,auto_click=True),0)
        events=[json.loads(x) for x in output.getvalue().splitlines()]
        self.assertEqual(batched.call_count,1)
        self.assertEqual(events[1]['request_id'],'one')
        self.assertEqual(events[1]['session_ocr_requests'],1)
        self.assertEqual(events[1]['ocr_passes'],1)
        self.assertFalse(events[1]['proposal_reused'])
        self.assertFalse(events[1]['authorization_granted'])
        self.assertTrue(all(x['status']=='error' for x in events[2:]))
        self.assertTrue(session.closed)


if __name__=='__main__':
    unittest.main()
