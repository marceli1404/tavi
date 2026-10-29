import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from PIL import Image
from tavi_target import candidates,score


class TargetPatchTests(unittest.TestCase):
    def test_frozen_fractional_edge_features_and_scores_are_exact(self):
        reference=json.loads(Path(__file__).with_name('test-fixtures').joinpath('target-patch-reference.json').read_text())
        y,x=np.indices((64,96))
        pixels=np.stack(((x*7+y*3)%256,(x*5+y*11)%256,(x*13+y*2)%256),axis=-1).astype('uint8')
        with tempfile.TemporaryDirectory() as folder:
            for mode,expected in reference['modes'].items():
                path=Path(folder)/(mode+'.png');Image.fromarray(pixels).convert(mode).save(path)
                actual,_=score(candidates(path,reference['ocr'],reference['task'],reference['target']))
                self.assertEqual(actual,expected,mode)
            case=reference['rounding_case']
            y,x=np.indices((case['size'][1],case['size'][0]))
            pixels=np.stack(((x*7+y*3)%256,(x*5+y*11)%256,(x*13+y*2)%256),axis=-1).astype('uint8')
            path=Path(folder)/'rounding.png';Image.fromarray(pixels).save(path)
            actual,_=score(candidates(path,case['ocr'],'Press Go','Go'))
            self.assertEqual(actual,case['expected'])

    def test_large_image_is_not_converted_to_full_frame_float_array(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'screen.png';Image.new('RGB',(3840,2160),(40,50,60)).save(path)
            original=np.asarray;sample_sizes=[]
            def sampled(value,*args,**kwargs):
                if isinstance(value,Image.Image):sample_sizes.append(value.width*value.height)
                return original(value,*args,**kwargs)
            ocr=dict(status='available',words=[dict(text='Go',x=1800,y=1000,width=40,height=20)])
            with patch('tavi_target.np.asarray',side_effect=sampled):
                items=candidates(path,ocr,'Press Go','Go')
            self.assertEqual(len(items),1)
            self.assertLess(max(sample_sizes),10000)

    def test_invalid_geometry_still_does_not_create_candidates(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'screen.png';Image.new('RGB',(96,64)).save(path)
            for x in (-1,float('nan'),95):
                ocr=dict(status='available',words=[dict(text='Go',x=x,y=0,width=20,height=10)])
                self.assertEqual(candidates(path,ocr,'Press Go','Go'),[])


if __name__=='__main__':unittest.main()
