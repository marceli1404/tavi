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

    def test_image_upload_permission_keeps_compact_encoding(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'source.png';Image.new('RGB',(640,480),'white').save(source)
            ocr=lambda image:dict(status='available',words=[dict(text='Go',x=20,y=20,width=40,height=20)])
            for fallback,expected in ((False,'fast'),(True,'compact')):
                with patch('tavi_compact.prepare',wraps=prepare) as call:
                    result=propose(source,'Press Go','Go',ocr_fn=ocr,allow_image_fallback=fallback)
                self.assertEqual(call.call_args.kwargs['compression'],expected)
                self.assertEqual(result['hosted_calls'],0)
                self.assertFalse(result['auto_click']['candidate_eligible'])

    def test_unknown_encoding_is_rejected_before_file_work(self):
        with self.assertRaisesRegex(ValueError,'compression'):
            prepare(Path('missing.png'),Path('out.png'),compression='lossy')


if __name__=='__main__':unittest.main()
