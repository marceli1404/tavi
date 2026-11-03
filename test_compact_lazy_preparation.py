"""Lossless lazy image fallback, captured-byte identity and unchanged decisions."""
import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image,ImageDraw,ImageFont
import tavi_compact as compact
from tavi_vision import prepare


class LazyPreparationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.image=self.root/'source.png'
        image=Image.new('RGB',(1200,700),'#f7f7f2');draw=ImageDraw.Draw(image)
        draw.rectangle((70,200,370,300),fill='#20231d')
        draw.text((170,225),'Go',font=ImageFont.load_default(size=36),fill='white');image.save(self.image)
        self.ocr=lambda path:dict(status='available',words=[dict(text='Go',x=170,y=231,width=45,height=32)])
        self.review=lambda p,*args:dict(decision='proceed',candidate_id=p['proposed']['id'],reason='Fits',proposal_id=p['proposal_id'])
        self.vision=lambda *args:dict(summary='Screen',visible_text=['Go'],target_candidates=[],uncertainties=[])

    def call(self,**kwargs):
        options=dict(ocr_fn=self.ocr,review_fn=self.review,vision_fn=self.vision,allow_image_fallback=True)
        options.update(kwargs)
        return compact.propose(self.image,'Press Go','Go',**options)

    def test_unused_fallback_preserves_pixels_coordinates_and_never_compresses_or_sends(self):
        reference=prepare(self.image,self.root/'reference.png',compression='compact')
        for execute in (False,True):
            with patch.object(compact,'_compact_image',side_effect=AssertionError('Unused image fallback')):
                result=self.call(execute=execute,auto_click=True)
            self.assertEqual(result['image']['pixels_sha256'],reference['pixels_sha256'])
            self.assertEqual(result['image']['prepared_size'],reference['prepared_size'])
            self.assertEqual(result['review_packet']['proposed']['x'],192.5)
            self.assertEqual(result['image_bytes_sent'],0)
            self.assertFalse(result['executed_actions']);self.assertFalse(result['auto_click']['candidate_eligible'])
            self.assertEqual(result['hosted_calls'],int(execute))

    def test_missing_target_fallback_sends_compact_identical_pixels_and_real_bytes(self):
        expected=prepare(self.image,self.root/'expected.png',compression='compact')
        seen=[]
        def vision(image,*args):
            with Image.open(image) as decoded:
                seen.append(hashlib.sha256(decoded.convert('RGB').tobytes()).hexdigest())
            self.assertEqual(image.stat().st_size,expected['prepared_bytes'])
            return self.vision(image,*args)
        result=self.call(execute=True,ocr_fn=lambda p:dict(status='available',words=[]),vision_fn=vision)
        self.assertEqual(seen,[expected['pixels_sha256']])
        self.assertEqual(result['image_bytes_sent'],expected['prepared_bytes'])
        self.assertEqual(result['image']['prepared_bytes'],expected['prepared_bytes'])
        self.assertEqual(result['hosted_calls'],1);self.assertFalse(result['executed_actions'])

    def test_review_requested_fallback_preserves_original_coordinate_mapping_after_resize(self):
        image=Image.open(self.image);image.resize((2400,1400)).save(self.image);image.close()
        def need_image(packet,*args):
            return dict(decision='need_image',candidate_id='',reason='Need context',proposal_id=packet['proposal_id'])
        result=self.call(execute=True,review_fn=need_image,
            vision_fn=lambda *a:dict(summary='Screen',visible_text=[],target_candidates=[dict(label='Go',x=100,y=80)],uncertainties=[]))
        self.assertEqual(result['image']['prepared_size'],[1600,933])
        self.assertEqual(result['mapped_image_candidates'],[dict(label='Go',x=150.,y=80*1400/933)])
        self.assertEqual(result['hosted_calls'],2);self.assertFalse(result['executed_actions'])

    def test_no_permission_or_explicit_review_rejection_never_encodes_image(self):
        for options in (dict(execute=False,ocr_fn=lambda p:dict(status='available',words=[])),
            dict(execute=True,allow_image_fallback=False,ocr_fn=lambda p:dict(status='available',words=[])),
            dict(execute=True,review_fn=lambda p,*a:dict(decision='reject',candidate_id='',reason='No',proposal_id=p['proposal_id']))):
            with patch.object(compact,'_compact_image',side_effect=AssertionError('Forbidden image upload')):
                result=self.call(**options)
            self.assertEqual(result['image_bytes_sent'],0)

    def test_transient_source_swap_cannot_change_prepared_pixels_under_original_identity(self):
        original=self.image.read_bytes();expected=prepare(self.image,self.root/'expected.png',compression='fast')
        alternate=io.BytesIO();Image.new('RGB',(1200,700),'black').save(alternate,format='PNG')
        def swap(*args,**kwargs):
            self.image.write_bytes(alternate.getvalue())
            try:return prepare(*args,**kwargs)
            finally:self.image.write_bytes(original)
        with patch.object(compact,'prepare',side_effect=swap):result=self.call()
        self.assertEqual(result['image_sha256'],hashlib.sha256(original).hexdigest())
        self.assertEqual(result['image']['pixels_sha256'],expected['pixels_sha256'])

    def test_persistent_source_change_still_discards_proposal(self):
        def change(packet,*args):
            self.image.write_bytes(b'changed')
            return self.review(packet,*args)
        with self.assertRaisesRegex(RuntimeError,'changed during review'):self.call(execute=True,review_fn=change)

    def test_fallback_reencoding_preserves_rgb_pixels_for_alpha_grayscale_and_exif_inputs(self):
        for mode in ('RGBA','L','RGB-exif'):
            image=Image.new('RGB',(1800,900),'#738697')
            if mode=='RGB-exif':
                exif=Image.Exif();exif[274]=6
                self.image=self.root/'rotated.jpg';image.save(self.image,exif=exif)
            else:
                self.image=self.root/(mode+'.png');image.convert(mode).save(self.image)
            expected_path=self.root/'expected.png';expected=prepare(self.image,expected_path,compression='compact')
            def vision(path,*args):
                with Image.open(path) as actual,Image.open(expected_path) as reference:
                    self.assertEqual(actual.size,reference.size)
                    self.assertEqual(actual.convert('RGB').tobytes(),reference.convert('RGB').tobytes())
                return self.vision(path,*args)
            result=self.call(execute=True,ocr_fn=lambda p:dict(status='available',words=[]),vision_fn=vision)
            self.assertEqual(result['image']['pixels_sha256'],expected['pixels_sha256'])

    def test_local_bitmap_is_compressed_before_any_image_review_callback(self):
        observations=[]
        def ocr(path):
            self.assertEqual(path.read_bytes()[:2],b'BM');observations.append('local_bitmap')
            return dict(status='available',words=[])
        def vision(path,*args):
            self.assertEqual(path.read_bytes()[:8],b'\x89PNG\r\n\x1a\n');observations.append('compressed_png')
            return self.vision(path,*args)
        result=self.call(execute=True,ocr_fn=ocr,vision_fn=vision)
        self.assertEqual(observations,['local_bitmap','compressed_png'])
        self.assertEqual(result['image_bytes_sent'],result['image']['prepared_bytes'])

    def test_retained_pixels_match_file_backed_features_and_are_closed_after_proposal(self):
        from tavi_target import candidates,_candidates_rgb
        observed=[];path_seen=[]
        def ocr(path):
            path_seen.append(path);return self.ocr(path)
        def inspect(rgb,ocr_result,task,target):
            expected=candidates(path_seen[0],ocr_result,task,target)
            actual=_candidates_rgb(rgb,ocr_result,task,target)
            self.assertEqual(actual,expected);observed.append(rgb);return actual
        with patch.object(compact,'_candidates_rgb',side_effect=inspect):result=self.call(ocr_fn=ocr)
        self.assertEqual(len(observed),1);self.assertFalse(result['executed_actions'])
        with self.assertRaises(ValueError):observed[0].getpixel((0,0))


if __name__=='__main__':unittest.main()
