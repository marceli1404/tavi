import json,os,tempfile,time,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from PIL import Image
import tavi_vision as vision

class EarlyVisionCacheTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.image=self.root/'source.png';Image.new('RGB',(2000,1000),'white').save(self.image)
  self.cache=self.root/'cache';self.ocr=Mock(return_value={'status':'available','text':'Install','words':[dict(text='Install',x=100,y=100,width=100,height=40)]})
  self.cloud=Mock(return_value=dict(summary='Screen',visible_text=[],target_candidates=[dict(label='Install',x=150,y=120)],uncertainties=[]))
 def call(self,**kwargs):
  options=dict(cache=self.cache,ocr_fn=self.ocr,hosted_fn=self.cloud,target='Install');options.update(kwargs)
  return vision.analyze(self.image,'Find install',**options)
 def entry(self):return next(self.cache.glob('*.json'))
 def test_warm_hit_skips_preparation_ocr_and_host(self):
  first=self.call()
  with patch.object(vision,'prepare',side_effect=AssertionError('Warm hit must not prepare')):second=self.call()
  self.assertTrue(second['cache_hit']);self.assertEqual(first['analysis'],second['analysis']);self.assertEqual(first['mapped_candidates'],second['mapped_candidates'])
  self.assertEqual(self.ocr.call_count,1);self.cloud.assert_not_called()
 def test_expired_and_future_cache_miss(self):
  self.call();entry=self.entry();os.utime(entry,(time.time()-400,time.time()-400));self.assertFalse(self.call()['cache_hit'])
  os.utime(entry,(time.time()+400,time.time()+400));self.assertFalse(self.call()['cache_hit']);self.assertEqual(self.ocr.call_count,3)
 def test_integer_age_keeps_warm_hit_despite_float_clock_rounding(self):
  first=self.call();entry=self.entry();modified_ns=entry.stat().st_mtime_ns
  # The previous float expression rejects a genuine zero-age observation if
  # the two timestamp conversions round in opposite directions.
  rounded_before=entry.stat().st_mtime-0.0000002384185791015625
  with patch.object(vision.time,'time',return_value=rounded_before),patch.object(vision.time,'time_ns',return_value=modified_ns),patch.object(vision,'prepare',side_effect=AssertionError('A zero-age observation must be reused')):
   second=self.call()
  self.assertTrue(second['cache_hit']);self.assertEqual(first['analysis'],second['analysis']);self.assertEqual(self.ocr.call_count,1)
 def test_nanosecond_boundaries_preserve_strict_expiry_and_future_rejection(self):
  first=self.call();entry=self.entry();saved=json.loads(entry.read_text());modified_ns=entry.stat().st_mtime_ns
  for age_ns,expected in ((0,True),(300_000_000_000,True),(300_000_000_100,False),(-100,False)):
   with self.subTest(age_ns=age_ns),patch.object(vision.time,'time_ns',return_value=modified_ns+age_ns):
    cached=vision._cached_result(entry,saved['key'],'hybrid',1600,300,first['image']['original_bytes'])
   self.assertEqual(cached is not None,expected)
 def test_disabled_cache_still_prepares(self):
  self.call()
  with patch.object(vision,'prepare',wraps=vision.prepare) as prepare:self.assertFalse(self.call(ttl=0)['cache_hit']);prepare.assert_called_once()
 def test_policy_change_invalidates(self):
  self.call()
  with patch.object(vision,'POLICY',vision.POLICY+' revised'):self.assertFalse(self.call()['cache_hit'])
  self.assertEqual(self.ocr.call_count,2)
 def test_bad_cached_geometry_recomputed(self):
  self.call();entry=self.entry();saved=json.loads(entry.read_text());saved['result']['image']['prepared_size']=[0,800];entry.write_text(json.dumps(saved));os.utime(entry,(time.time()-1,time.time()-1))
  self.assertFalse(self.call()['cache_hit']);self.assertEqual(self.ocr.call_count,2)
 def test_mapping_rebuilt_from_validated_analysis(self):
  first=self.call();entry=self.entry();saved=json.loads(entry.read_text());saved['result']['mapped_candidates']=[dict(label='Wrong',x=99999,y=99999)];entry.write_text(json.dumps(saved));os.utime(entry,(time.time()-1,time.time()-1))
  second=self.call();self.assertTrue(second['cache_hit']);self.assertEqual(first['mapped_candidates'],second['mapped_candidates'])
 def test_captured_bytes_and_cache_identity_match_despite_file_change(self):
  original=vision.prepare;expected=self.call()['image']['pixels_sha256']
  self.entry().unlink()
  def replace_source(*args,**kwargs):
   Image.new('RGB',(2000,1000),'black').save(self.image)
   return original(*args,**kwargs)
  with patch.object(vision,'prepare',side_effect=replace_source):snapshot=self.call()
  self.assertEqual(snapshot['image']['pixels_sha256'],expected)
  changed=self.call();self.assertFalse(changed['cache_hit']);self.assertNotEqual(changed['image']['pixels_sha256'],expected)
 def test_action_claim_in_cache_recomputed(self):
  self.call();entry=self.entry();saved=json.loads(entry.read_text());saved['result']['executed_actions']=True;entry.write_text(json.dumps(saved));os.utime(entry,(time.time()-1,time.time()-1))
  result=self.call();self.assertFalse(result['cache_hit']);self.assertFalse(result['executed_actions']);self.assertEqual(self.ocr.call_count,2)
 def test_source_geometry_cannot_share_downsample_cache(self):
  self.call();Image.new('RGB',(1000,2000),'white').save(self.image)
  result=self.call();self.assertFalse(result['cache_hit']);self.assertEqual(result['image']['original_size'],[1000,2000]);self.assertEqual(self.ocr.call_count,2)
 def test_cached_hosted_observation_does_not_send_again(self):
  self.call(mode='codex',execute=True)
  with patch.object(vision,'prepare',side_effect=AssertionError('Cached hosted observation')):result=self.call(mode='codex',execute=False)
  self.assertTrue(result['cache_hit']);self.assertFalse(result['hosted_request_this_call']);self.assertFalse(result['executed_actions']);self.cloud.assert_called_once()

if __name__=='__main__':unittest.main()
