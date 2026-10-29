import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import Mock,patch
import numpy as np

try:
    from PIL import Image,ImageDraw,ImageFont
except ImportError: Image=None
from tavi_compact import propose,hosted_review,check_review
from tavi_target import load,DEFAULT

@unittest.skipUnless(Image,'Optional Pillow required')
class CompactTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.image=self.root/'screen.png'
        im=Image.new('RGB',(1200,700),'#f7f7f2'); draw=ImageDraw.Draw(im)
        draw.rectangle((70,200,370,300),fill='#20231d')
        font=ImageFont.load_default(size=36)
        draw.text((170,225),'Go',font=font,fill='white'); im.save(self.image)
        self.ocr=Mock(return_value={'status':'available','words':[dict(text='Go',x=170,y=231,width=45,height=32)]})
        self.vision=Mock(return_value=dict(summary='Screen',visible_text=['Go'],target_candidates=[],uncertainties=[]))
        self.review=Mock(side_effect=lambda packet,*args:dict(decision='proceed',candidate_id=packet['proposed']['id'],reason='Target fits task',proposal_id=packet['proposal_id']))

    def call(self,**kwargs):
        options=dict(ocr_fn=self.ocr,review_fn=self.review,vision_fn=self.vision)
        options.update(kwargs)
        return propose(self.image,'Press Go','Go',**options)

    def test_local_proposal_sends_nothing(self):
        result=self.call()
        self.assertEqual(result['status'],'pending_current_codex_review')
        self.assertEqual(result['image_bytes_sent'],0)
        self.assertEqual(result['hosted_calls'],0)
        self.assertGreater(result['confidence']['percent'],90)
        self.assertLess(result['confidence']['percent'],100)
        self.review.assert_not_called(); self.vision.assert_not_called()

    def test_enabled_policy_withholds_unqualified_synthetic_probability(self):
        result=self.call(auto_click=True)
        self.assertFalse(result['auto_click']['candidate_eligible'])
        self.assertIn('target_probability_not_field_qualified',result['auto_click']['reasons'])
        self.assertEqual(result['status'],'pending_current_codex_review')
        self.assertFalse(result['executed_actions']); self.assertEqual(result['hosted_calls'],0)

    def test_explicit_rejection_blocks_automatic_candidate(self):
        self.review.side_effect=lambda packet,*args:dict(decision='reject',candidate_id='',reason='No',proposal_id=packet['proposal_id'])
        result=self.call(auto_click=True,execute=True)
        self.assertFalse(result['auto_click']['candidate_eligible'])
        self.assertEqual(result['status'],'target_review_rejected')

    def test_text_review_has_no_image_in_workspace_or_packet(self):
        def review(packet,model,effort,folder):
            self.assertEqual(list(folder.iterdir()),[])
            text=json.dumps(packet)
            self.assertNotIn(str(self.image),text); self.assertNotIn('base64',text)
            return dict(decision='proceed',candidate_id=packet['proposed']['id'],proposal_id=packet['proposal_id'],reason='Fits')
        result=self.call(execute=True,review_fn=review)
        self.assertEqual(result['status'],'target_reviewed_proceed')
        self.assertFalse(result['executed_actions']); self.assertEqual(result['image_bytes_sent'],0)

    def test_missing_target_never_silently_sends_image(self):
        self.ocr.return_value['words']=[]
        result=self.call(execute=True)
        self.assertEqual(result['status'],'needs_image_review')
        self.review.assert_not_called(); self.vision.assert_not_called()

    def test_image_fallback_requires_explicit_option(self):
        self.ocr.return_value['words']=[]
        result=self.call(execute=True,allow_image_fallback=True)
        self.assertGreater(result['image_bytes_sent'],0)
        self.assertEqual(result['status'],'image_observations_for_host_review')

    def test_review_can_request_image_without_upload(self):
        self.review.side_effect=lambda packet,*args:dict(decision='need_image',candidate_id='',reason='More context',proposal_id=packet['proposal_id'])
        result=self.call(execute=True)
        self.assertEqual(result['status'],'needs_image_review')
        self.vision.assert_not_called()

    def test_no_permission_to_change_target(self):
        with self.assertRaises(ValueError):
            check_review(dict(decision='proceed',candidate_id='other',reason='x',proposal_id='p'),'candidate-0','p')

    def test_stale_proposal_response_rejected(self):
        with self.assertRaises(ValueError):
            check_review(dict(decision='proceed',candidate_id='candidate-0',reason='x',proposal_id='old'),'candidate-0','new')

    def test_image_change_during_review_rejected(self):
        def review(packet,*args):
            self.image.write_bytes(b'changed')
            return dict(decision='proceed',candidate_id=packet['proposed']['id'],reason='x',proposal_id=packet['proposal_id'])
        with self.assertRaises(RuntimeError): self.call(execute=True,review_fn=review)

    def test_ambiguous_targets_not_sent_for_text_review(self):
        word=self.ocr.return_value['words'][0]
        self.ocr.return_value['words']=[word,word.copy()]
        result=self.call(execute=True)
        self.assertIn('ambiguous_targets',result['review_reasons'])
        self.review.assert_not_called()

    def test_negative_context_withholds_proposal(self):
        self.ocr.return_value['words'].append(dict(text='Disabled',x=110,y=330,width=120,height=32))
        result=self.call(execute=True)
        self.assertIn('negative_context',result['review_reasons'])
        self.review.assert_not_called()

    def test_invalid_ocr_coordinates_ignored(self):
        self.ocr.return_value['words'][0]['x']=float('nan')
        result=self.call()
        self.assertIn('no_exact_text_target',result['review_reasons'])

    def test_cli_review_omits_image_and_rejects_tool_use(self):
        def run(command,**kwargs):
            self.assertNotIn('--image',command); self.assertNotIn('-i',command)
            output=Path(command[command.index('--output-last-message')+1])
            output.write_text('{}')
            return type('Result',(),dict(returncode=0,stdout=json.dumps({'item':{'type':'command_execution'}})))()
        with patch('tavi.codex_command',return_value=['codex']),patch('tavi_compact.subprocess.run',side_effect=run):
            with self.assertRaises(RuntimeError): hosted_review({},'test','low',self.root)

    def test_model_corruption_rejected(self):
        folder=self.root/'model'; shutil.copytree(DEFAULT,folder)
        with (folder/'weights.npz').open('ab') as stream: stream.write(b'corrupt')
        with self.assertRaises(ValueError): load(folder)

    def test_nonfinite_model_rejected_even_with_updated_digest(self):
        folder=self.root/'model'; shutil.copytree(DEFAULT,folder)
        metadata,arrays=load(folder); arrays['weight'][0]=float('nan')
        np.savez(folder/'weights.npz',**arrays)
        metadata['weights_sha256']=hashlib.sha256((folder/'weights.npz').read_bytes()).hexdigest()
        (folder/'model.json').write_text(json.dumps(metadata))
        with self.assertRaises(ValueError): load(folder)

    def test_reviews_are_not_reused_as_authorization(self):
        first=self.call(execute=True); second=self.call(execute=True)
        self.assertEqual(self.review.call_count,2)
        self.assertNotEqual(first['proposal_id'],second['proposal_id'])

    def test_allow_fallback_flag_alone_does_not_execute(self):
        self.ocr.return_value['words']=[]
        result=self.call(allow_image_fallback=True)
        self.assertEqual(result['hosted_calls'],0)
        self.vision.assert_not_called()

    def test_probability_scope_is_explicit(self):
        result=self.call()
        self.assertFalse(result['confidence']['field_validated'])
        self.assertEqual(result['confidence']['scope'],'synthetic_control_target_match')

    def test_explicit_noninteractive_context_withholds_high_score(self):
        self.ocr.return_value['words']+= [dict(text='Illustration',x=90,y=340,width=150,height=30),
            dict(text='only.',x=260,y=340,width=70,height=30)]
        result=self.call(execute=True)
        self.assertIn('noninteractive_context',result['review_reasons'])
        self.assertEqual(result['status'],'needs_image_review')
        self.review.assert_not_called()

if __name__=='__main__': unittest.main()
