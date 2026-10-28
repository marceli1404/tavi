import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

try:
    from PIL import Image
except ImportError:
    Image = None
from tavi_vision import analyze, validate

@unittest.skipUnless(Image, 'Install requirements-vision.txt for screenshot tests')
class VisionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.image=self.root/'screen.png'
        Image.new('RGB',(2000,1000),'white').save(self.image)
        self.ocr=Mock(return_value={'status':'available','text':'Install','words':[
            {'text':'Install','x':100,'y':100,'width':100,'height':40}]})
        self.cloud=Mock(return_value={'summary':'An install screen','visible_text':['Install'],
            'target_candidates':[{'label':'Install','x':150,'y':120}], 'uncertainties':[]})

    def call(self,**kwargs):
        options=dict(ocr_fn=self.ocr,hosted_fn=self.cloud,cache=self.root/'cache')
        options.update(kwargs)
        return analyze(self.image,'Find install',**options)

    def test_exact_local_match_maps_original_coordinates(self):
        result=self.call(target='Install',execute=True)
        self.cloud.assert_not_called()
        self.assertEqual(result['mapped_candidates'][0]['x'],187.5)
        self.assertFalse(result['executed_actions'])

    def test_local_never_sends(self):
        self.call(mode='local',execute=True)
        self.cloud.assert_not_called()

    def test_plan_does_not_poison_execution(self):
        self.assertEqual(self.call()['provider'],'plan')
        self.assertEqual(self.call(execute=True)['provider'],'codex')
        self.cloud.assert_called_once()

    def test_cache_and_invalidation(self):
        self.call(execute=True)
        result=self.call(execute=True)
        self.assertTrue(result['cache_hit'])
        self.assertFalse(result['hosted_request_this_call'])
        self.call(execute=True,model='another-model')
        self.call(execute=True,effort='medium')
        self.call(execute=True,max_edge=1200)
        analyze(self.image,'Another task',execute=True,cache=self.root/'cache',ocr_fn=self.ocr,hosted_fn=self.cloud)
        Image.new('RGB',(2000,1000),'black').save(self.image)
        self.call(execute=True)
        self.assertEqual(self.cloud.call_count,6)

    def test_ambiguous_ocr_escalates(self):
        word=self.ocr.return_value['words'][0]
        self.ocr.return_value['words']=[word,word.copy()]
        self.assertEqual(self.call(target='Install',execute=True)['provider'],'codex')

    def test_out_of_bounds_rejected(self):
        self.cloud.return_value['target_candidates'][0]['x']=9000
        with self.assertRaises(ValueError): self.call(execute=True)

    def test_corrupt_cache_recomputed(self):
        self.call(execute=True)
        next((self.root/'cache').glob('*.json')).write_text('corrupt')
        self.call(execute=True)
        self.assertEqual(self.cloud.call_count,2)

    def test_expired_and_disabled_cache(self):
        self.call(execute=True)
        self.call(execute=True,ttl=0)
        self.assertEqual(self.cloud.call_count,2)

    def test_ocr_unavailable_is_visible(self):
        self.ocr.return_value={'status':'unavailable'}
        result=self.call(mode='local')
        self.assertEqual(result['ocr_status'],'unavailable')
        self.assertEqual(result['analysis']['visible_text'],[])

    def test_unavailable_ocr_escalates_only_when_authorized(self):
        self.ocr.return_value={'status':'unavailable'}
        self.assertEqual(self.call()['provider'],'plan')
        self.cloud.assert_not_called()
        self.assertEqual(self.call(execute=True)['provider'],'codex')

    def test_target_and_mode_separate_cache(self):
        self.call(target='Install')
        self.assertEqual(self.call(target='Other')['provider'],'plan')
        self.assertEqual(self.call(mode='local')['analysis']['target_candidates'],[])

    def test_invalid_task_and_size_rejected(self):
        with self.assertRaises(ValueError): self.call(max_edge=50)
        with self.assertRaises(ValueError): analyze(self.image,' ')

    def test_nonfinite_coordinates_rejected(self):
        self.cloud.return_value['target_candidates'][0]['y']=float('nan')
        with self.assertRaises(ValueError): self.call(execute=True)

if __name__=='__main__': unittest.main()
