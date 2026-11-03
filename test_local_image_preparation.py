from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from PIL import Image
from tavi_vision import prepare
from tavi_compact import propose


class LocalImagePreparationTests(unittest.TestCase):
    def test_fast_png_has_identical_pixels_geometry_and_digest(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);y,x=np.indices((720,1280))
            pixels=np.stack(((x*7+y*3)%256,(x*5+y*11)%256,(x*13+y*2)%256),axis=-1).astype('uint8')
            source=root/'source.png';Image.fromarray(pixels).save(source)
            a=prepare(source,root/'compact.png',512)
            b=prepare(source,root/'fast.png',512,compression='fast')
            for key in ('original_size','prepared_size','original_bytes','pixels_sha256'):
                self.assertEqual(a[key],b[key])
            with Image.open(root/'compact.png') as first,Image.open(root/'fast.png') as second:
                np.testing.assert_array_equal(np.asarray(first),np.asarray(second))

    def test_image_upload_permission_keeps_actual_upload_compact_and_pixels_identical(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source.png';Image.new('RGB',(640,480),'white').save(source)
            reference=prepare(source,root/'reference.png')
            uploaded=[]
            def vision(image,*args):
                self.assertEqual(image.read_bytes()[:8],b'\x89PNG\r\n\x1a\n')
                self.assertEqual(image.stat().st_size,reference['prepared_bytes'])
                with Image.open(image) as actual,Image.open(root/'reference.png') as expected:
                    self.assertEqual(actual.tobytes(),expected.tobytes())
                uploaded.append(image.stat().st_size)
                return dict(summary='Screen',visible_text=[],target_candidates=[],uncertainties=[])
            empty_ocr=lambda image:dict(status='available',words=[])
            for fallback,execute in ((False,False),(True,False),(False,True),(True,True)):
                before=len(uploaded)
                result=propose(source,'Press Go','Go',ocr_fn=empty_ocr,allow_image_fallback=fallback,execute=execute,vision_fn=vision)
                expected_upload=fallback and execute
                self.assertEqual(len(uploaded)-before,int(expected_upload))
                self.assertEqual(result['image_bytes_sent'],reference['prepared_bytes'] if expected_upload else 0)
                self.assertEqual(result['hosted_calls'],int(expected_upload))
                self.assertFalse(result['executed_actions']);self.assertFalse(result['auto_click']['candidate_eligible'])

    def test_unknown_encoding_is_rejected_before_file_work(self):
        with self.assertRaisesRegex(ValueError,'compression'):
            prepare(Path('missing.png'),Path('out.png'),compression='lossy')


if __name__=='__main__':unittest.main()
