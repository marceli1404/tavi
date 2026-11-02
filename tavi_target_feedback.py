"""Explicit local operator feedback; never captures, clicks, trains or qualifies."""
from pathlib import Path
from datetime import datetime,timezone
from collections import defaultdict,Counter
import hashlib,json,math,uuid
FORMAT='tavi-target-feedback-v1'
MATCH={'correct','incorrect','unverified'}
OUTCOME={'success','failure','unverified'}
ROLES={'button','link','tab','checkbox','switch','radio','menuitem','textbox','combobox','unknown','noninteractive'}
BINDING=('weights_sha256','feature_version','image_sha256','task_sha256','requested_label_sha256','candidate_id','candidate_label_sha256','original_size','x','y','raw_score')

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()).hexdigest()
def text(value,limit=4096):
 if not isinstance(value,str) or not value.strip() or len(value)>limit:raise ValueError('Invalid feedback text')
 return value

def hexhash(value):
 if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):raise ValueError('Invalid hash binding')
 return value

def number(value):
 if type(value) not in (int,float) or not math.isfinite(value):raise ValueError('Invalid numeric observation')
 return value

def read_json(path):
 path=Path(path)
 with path.open('rb') as stream:raw=stream.read(2*1024*1024+1)
 if len(raw)>2*1024*1024:raise ValueError('Feedback input exceeds2MB')
 return json.loads(raw.decode('utf-8-sig'))

def _validate(event):
 if not isinstance(event,dict) or event.get('format')!=FORMAT:raise ValueError('Unsupported feedback record')
 expected=set(BINDING)|{'format','id','timestamp','source','proposal_id','proposal_sha256','target_match','action_outcome','actual_role','evidence','automatic_probability_qualified','qualification_changed','case_id'}
 if set(event)!=expected:raise ValueError('Unexpected feedback fields')
 uuid.UUID(event['id'])
 for k in ('weights_sha256','image_sha256','task_sha256','requested_label_sha256','candidate_label_sha256','proposal_sha256'):hexhash(event[k])
 text(event['feature_version'],100);text(event['candidate_id'],200);text(event['proposal_id'],200);text(event['evidence'],4000)
 width,height=event['original_size']
 if type(width) is not int or type(height) is not int or width<=0 or height<=0 or width*height>24_000_000 or not 0<=number(event['x'])<width or not 0<=number(event['y'])<height:raise ValueError('Invalid recorded geometry')
 if datetime.fromisoformat(event['timestamp']).tzinfo is None:raise ValueError('Feedback timestamp requires timezone')
 score=number(event['raw_score'])
 if not 0<=score<=1:raise ValueError('Raw score outside0–1')
 if event['target_match'] not in MATCH or event['action_outcome'] not in OUTCOME or event['actual_role'] not in ROLES:raise ValueError('Invalid outcome label')
 if event.get('source')!='operator-entered' or event.get('automatic_probability_qualified') is not False or event.get('qualification_changed') is not False:raise ValueError('Feedback cannot qualify actions')
 if event['case_id']!=digest({k:event[k] for k in BINDING}):raise ValueError('Observation binding mismatch')
 return event

def validate(event):
 try:return _validate(event)
 except (KeyError,TypeError,AttributeError,OverflowError) as error:raise ValueError('Malformed feedback record') from error

def _record(directory,proposal,observation):
 if not isinstance(proposal,dict) or not isinstance(observation,dict) or set(observation)!={'proposal_id','candidate_id','target_match','action_outcome','actual_role','evidence'}:raise ValueError('Expected proposal_id/candidate_id/target_match/action_outcome/actual_role/evidence only')
 packet=proposal['review_packet'];candidate=packet['proposed'];model=proposal['model_evidence'];confidence=proposal['confidence']
 if not isinstance(candidate,dict) or packet['proposal_id']!=proposal['proposal_id']:raise ValueError('Missing or mismatched proposed target')
 if observation['proposal_id']!=proposal['proposal_id'] or observation['candidate_id']!=candidate['id']:raise ValueError('Observation belongs to another proposal or candidate')
 width,height=proposal['image']['original_size']
 if type(width) is not int or type(height) is not int or width<=0 or height<=0 or width*height>24_000_000:raise ValueError('Invalid original geometry')
 x=number(candidate['x']);y=number(candidate['y'])
 if not 0<=x<width or not 0<=y<height:raise ValueError('Candidate outside original screenshot')
 hash_text=lambda value:hashlib.sha256(text(value,8000).encode()).hexdigest()
 event=dict(format=FORMAT,id=str(uuid.uuid4()),timestamp=datetime.now(timezone.utc).isoformat(),source='operator-entered',
  weights_sha256=hexhash(model['weights_sha256']),feature_version=text(model['feature_version'],100),image_sha256=hexhash(proposal['image_sha256']),
  task_sha256=hash_text(packet['task']),requested_label_sha256=hash_text(packet['requested_label']),candidate_id=text(candidate['id'],200),candidate_label_sha256=hash_text(candidate['label']),
  original_size=[width,height],x=0.0 if x==0 else float(x),y=0.0 if y==0 else float(y),raw_score=0.0 if number(confidence['probability'])==0 else float(number(confidence['probability'])),proposal_id=text(proposal['proposal_id'],200),proposal_sha256=digest(proposal),
  target_match=observation['target_match'],action_outcome=observation['action_outcome'],actual_role=observation['actual_role'],evidence=observation['evidence'],automatic_probability_qualified=False,qualification_changed=False)
 event['case_id']=digest({k:event[k] for k in BINDING});validate(event)
 directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
 with (directory/(event['id']+'.json')).open('x',encoding='utf-8') as f:json.dump(event,f,indent=2)
 return event

def record(directory,proposal,observation):
 try:return _record(directory,proposal,observation)
 except (KeyError,TypeError,AttributeError,OverflowError) as error:raise ValueError('Malformed proposal or observation') from error

def outcome_counts(groups,field,known):
 counts=Counter()
 for events in groups:
  values={e[field] for e in events if e[field] in known}
  counts[next(iter(values)) if len(values)==1 else 'conflicted' if values else 'unverified']+=1
 return {k:counts[k] for k in sorted(known)}|dict(unverified=counts['unverified'],conflicted=counts['conflicted'])

def describe(events):
 groups=defaultdict(list)
 for e in events:groups[e['case_id']].append(e)
 grouped=list(groups.values());match=outcome_counts(grouped,'target_match',{'correct','incorrect'});action=outcome_counts(grouped,'action_outcome',{'success','failure'})
 n=match['correct']+match['incorrect'];a=action['success']+action['failure']
 return dict(events=len(events),distinct_observations=len(groups),repeated_observation_events=len(events)-len(groups),unique_image_hashes=len({e['image_sha256'] for e in events}),unique_image_task_bindings=len({(e['image_sha256'],e['task_sha256'],e['requested_label_sha256']) for e in events}),target_match=match,target_match_known=n,operator_recorded_target_match_rate=match['correct']/n if n else None,action_outcome=action,action_outcome_known=a,operator_recorded_action_success_rate=action['success']/a if a else None)

def summarize(directory):
 directory=Path(directory)
 if not directory.is_dir():raise ValueError('Feedback directory missing')
 files=sorted(directory.glob('*.json'))
 if len(files)>10000:raise ValueError('Feedback summary exceeds10000files')
 if sum(p.stat().st_size for p in files)>32*1024*1024:raise ValueError('Feedback summary exceeds32MB')
 ids={};duplicate_files=0
 for path in files:
  event=validate(read_json(path))
  if event['id'] in ids:
   if ids[event['id']]!=event:raise ValueError('Conflicting event ID')
   duplicate_files+=1
  else:ids[event['id']]=event
 groups=defaultdict(list)
 for e in ids.values():groups[(e['weights_sha256'],e['feature_version'])].append(e)
 models=[]
 for (weights,version),events in sorted(groups.items()):
  bins=[]
  for low,high in ((0,.5),(.5,.9),(.9,.95),(.95,1.0)):
   subset=[e for e in events if low<=e['raw_score'] and (e['raw_score']<high or high==1.0 and e['raw_score']==1.0)]
   bins.append(dict(raw_score_range=[low,high],**describe(subset)))
  models.append(dict(weights_sha256=weights,feature_version=version,**describe(events),score_bins=bins,automatic_probability_qualified=False))
 return dict(format='tavi-target-feedback-summary-v1',files=len(files),unique_events=len(ids),duplicate_event_files=duplicate_files,models=models,calibration_status='operator_observations_only_unqualified',automatic_probability_qualified=False,qualification_changed=False,scope='Self-selected operator assessments of supplied proposals; not authenticated host facts, independent trials, calibrated action-success probabilities or full-screen target coverage. No model/action policy changes.')
