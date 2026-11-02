import unittest,tempfile,json,copy,subprocess,sys
from pathlib import Path
from tavi_target_feedback import record,summarize

class TargetFeedbackTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.proposal=dict(proposal_id='proposal-1',image_sha256='b'*64,model_evidence=dict(weights_sha256='a'*64,feature_version='target-v1'),confidence=dict(probability=.99,percent=99),image=dict(original_size=[100,100]),review_packet=dict(proposal_id='proposal-1',task='PRIVATE-TASK-TEXT',requested_label='PRIVATE-LABEL',proposed=dict(id='candidate-1',label='PRIVATE-LABEL',x=25,y=30)))
  self.observation=dict(proposal_id='proposal-1',candidate_id='candidate-1',target_match='correct',action_outcome='unverified',actual_role='button',evidence='Observed control state.')
 def save(self,p=None,o=None):
  proposal=p or self.proposal
  return record(self.root/'events',proposal,o if o is not None else self.observation|dict(proposal_id=proposal['proposal_id'],candidate_id=proposal['review_packet']['proposed']['id']))
 def test_hash_bound_minimal_record_and_no_input_mutation(self):
  before=copy.deepcopy(self.proposal);e=self.save();self.assertEqual(self.proposal,before);self.assertEqual(e['weights_sha256'],'a'*64);self.assertFalse(e['qualification_changed']);self.assertFalse(e['automatic_probability_qualified'])
  raw=next((self.root/'events').glob('*.json')).read_text();self.assertNotIn('PRIVATE-TASK-TEXT',raw);self.assertNotIn('PRIVATE-LABEL',raw);self.assertNotIn('review_packet',raw)
 def test_repeated_proposals_count_once_and_conflicts_stay_visible(self):
  self.save();p=copy.deepcopy(self.proposal);p['proposal_id']='another';p['review_packet']['proposal_id']='another';self.save(p)
  m=summarize(self.root/'events')['models'][0];self.assertEqual(m['events'],2);self.assertEqual(m['distinct_observations'],1);self.assertEqual(m['target_match_known'],1)
  o=self.observation|dict(target_match='incorrect');self.save(o=o);m=summarize(self.root/'events')['models'][0];self.assertEqual(m['target_match']['conflicted'],1);self.assertIsNone(m['operator_recorded_target_match_rate'])
 def test_unknown_target_and_action_outcomes_are_separate(self):
  self.save(o=self.observation|dict(target_match='unverified',action_outcome='success'))
  m=summarize(self.root/'events')['models'][0];self.assertEqual(m['target_match_known'],0);self.assertIsNone(m['operator_recorded_target_match_rate']);self.assertEqual(m['operator_recorded_action_success_rate'],1)
 def test_equivalent_numeric_json_does_not_inflate_observations(self):
  p=copy.deepcopy(self.proposal);p['confidence']['probability']=1;self.save(p)
  p['confidence']['probability']=1.0;p['review_packet']['proposed']['x']=25.0;self.save(p)
  self.assertEqual(summarize(self.root/'events')['models'][0]['distinct_observations'],1)
 def test_observation_must_name_the_same_proposal_and_candidate(self):
  for field in ('proposal_id','candidate_id'):
   with self.assertRaises(ValueError):self.save(o=self.observation|{field:'another'})
  self.assertFalse((self.root/'events').exists())
 def test_models_do_not_share_denominators(self):
  self.save();p=copy.deepcopy(self.proposal);p['model_evidence']['weights_sha256']='c'*64;self.save(p,o=self.observation|dict(target_match='incorrect'))
  groups=summarize(self.root/'events')['models'];self.assertEqual(len(groups),2);self.assertEqual([g['target_match_known'] for g in groups],[1,1])
 def test_raw_unrounded_score_binning(self):
  for probability in (.949999,.95,1.):
   p=copy.deepcopy(self.proposal);p['confidence']['probability']=probability;self.save(p)
  m=summarize(self.root/'events')['models'][0];self.assertEqual(m['score_bins'][2]['distinct_observations'],1);self.assertEqual(m['score_bins'][3]['distinct_observations'],2);self.assertFalse(m['automatic_probability_qualified'])
 def test_invalid_scores_bindings_and_extra_action_flags_never_write(self):
  for probability in (float('nan'),1.01,True):
   p=copy.deepcopy(self.proposal);p['confidence']['probability']=probability
   with self.assertRaises(ValueError):self.save(p)
  p=copy.deepcopy(self.proposal);p['review_packet']['proposal_id']='other'
  with self.assertRaises(ValueError):self.save(p)
  with self.assertRaises(ValueError):self.save(o=self.observation|dict(enable_click=True))
  self.assertFalse((self.root/'events').exists())
 def test_edited_qualification_record_rejected_and_copied_file_not_inflated(self):
  e=self.save();files=list((self.root/'events').glob('*.json'));(self.root/'events'/'copy.json').write_bytes(files[0].read_bytes());s=summarize(self.root/'events');self.assertEqual(s['unique_events'],1);self.assertEqual(s['duplicate_event_files'],1)
  e['automatic_probability_qualified']=True;files[0].write_text(json.dumps(e))
  with self.assertRaises(ValueError):summarize(self.root/'events')
 def test_cli_works_without_config_or_inventory(self):
  proposal=self.root/'proposal.json';obs=self.root/'observation.json';proposal.write_text(json.dumps(self.proposal));obs.write_text(json.dumps(self.observation));script=Path(__file__).with_name('tavi.py')
  p=subprocess.run([sys.executable,str(script),'--config',str(self.root/'missing.json'),'target-feedback',str(proposal),str(obs),'--directory',str(self.root/'events')],capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stderr);self.assertFalse(json.loads(p.stdout)['qualification_changed'])
  p=subprocess.run([sys.executable,str(script),'--config',str(self.root/'missing.json'),'target-feedback-summary',str(self.root/'events')],capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(json.loads(p.stdout)['unique_events'],1)
if __name__=='__main__':unittest.main()
