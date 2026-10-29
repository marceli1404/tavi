"""Automatic routine-button policy and host-driver callbacks. No OS input backend is bundled."""
from datetime import datetime,timezone
import math
from pathlib import Path
import json
import threading

THRESHOLD=.95

def configured(path):
    path=Path(path)
    if not path.exists(): return False
    policy=json.loads(path.read_text(encoding='utf-8-sig')).get('auto_click',{})
    if not policy: return False
    if not isinstance(policy,dict) or type(policy.get('enabled')) is not bool:
        raise ValueError('auto_click.enabled must be boolean')
    if policy.get('threshold_percent',95)!=95 or policy.get('routine_buttons_only',True) is not True:
        raise ValueError('Automatic click policy requires95% and routine buttons only')
    return policy['enabled']

def plan(proposal,enabled=False):
    if not isinstance(proposal,dict):
        return dict(enabled=enabled is True,threshold_percent=95,candidate_eligible=False,
            reasons=['invalid_proposal'],requires_live_host_check=True)
    reasons=[]
    if enabled is not True: reasons.append('automatic_click_disabled')
    confidence=proposal.get('confidence')
    probability=confidence.get('probability') if isinstance(confidence,dict) else None
    if not isinstance(confidence,dict) or confidence.get('automatic_probability_qualified') is not True:
        reasons.append('target_probability_not_field_qualified')
    if type(probability) not in (int,float) or not math.isfinite(probability) or not 0<=probability<=1:
        reasons.append('missing_or_invalid_unrounded_confidence')
    elif probability<THRESHOLD: reasons.append('below_95_percent')
    if proposal.get('eligible_compact_review') is not True or proposal.get('review_reasons')!=[]:
        reasons.append('target_checks_withheld')
    if proposal.get('status') not in ('pending_current_codex_review','target_reviewed_proceed','automatic_click_candidate'):
        reasons.append('target_not_ready')
    packet=proposal.get('review_packet'); packet=packet if isinstance(packet,dict) else {}
    target=packet.get('proposed'); target=target if isinstance(target,dict) else {}
    if not proposal.get('proposal_id') or packet.get('proposal_id')!=proposal.get('proposal_id'):
        reasons.append('proposal_binding_invalid')
    if not target.get('id') or not isinstance(target.get('label'),str) or target['label'].casefold()!=str(packet.get('requested_label','')).casefold():
        reasons.append('target_binding_invalid')
    image_hash=proposal.get('image_sha256')
    if not isinstance(image_hash,str) or len(image_hash)!=64 or any(c not in '0123456789abcdef' for c in image_hash):
        reasons.append('image_binding_invalid')
    if proposal.get('executed_actions') is not False: reasons.append('action_already_attempted_or_unknown')
    review=proposal.get('review')
    if review is not None and (not isinstance(review,dict) or review.get('decision')!='proceed' or
        review.get('candidate_id')!=target.get('id') or review.get('proposal_id')!=proposal.get('proposal_id')):
        reasons.append('review_withheld')
    try:
        width,height=proposal['image']['original_size']
        if any(type(target[k]) not in (int,float) or not math.isfinite(target[k]) for k in ('x','y')) or not 0<=target['x']<width or not 0<=target['y']<height:
            reasons.append('invalid_target_coordinates')
    except (KeyError,TypeError,ValueError): reasons.append('invalid_target_coordinates')
    return dict(enabled=enabled is True,threshold_percent=95,candidate_eligible=not reasons,reasons=reasons,
        requires_live_host_check=True,scope='routine authorized buttons only; confidence is not action safety')

class AutoClickSession:
    """The host supplies inspect/click/verify callbacks through its supported computer-use driver.

    inspect returns trusted current UI facts, never claims derived just from OCR text.
    Every click attempt consumes the proposal, including uncertain/failed outcomes.
    """
    def __init__(self,enabled=False,max_age_seconds=5,clock=None):
        if type(enabled) is not bool: raise ValueError('enabled must be boolean')
        if type(max_age_seconds) not in (int,float) or not 0<max_age_seconds<=30: raise ValueError('Action age limit must be greater than0 and at most30 seconds')
        self.enabled=enabled; self.max_age=max_age_seconds; self.clock=clock or (lambda:datetime.now(timezone.utc))
        self.consumed=set()
        self._lock=threading.Lock()

    def perform(self,proposal,*,task,inspect,click,verify):
        with self._lock:
            return self._perform(proposal,task=task,inspect=inspect,click=click,verify=verify)

    def _perform(self,proposal,*,task,inspect,click,verify):
        gate=plan(proposal,self.enabled)
        def withheld(reason): return dict(status='withheld',reason=reason,attempted=False,executed_actions=False)
        if not gate['candidate_eligible']: return withheld(','.join(gate['reasons']))
        identity=proposal['proposal_id']
        if identity in self.consumed: return withheld('proposal_already_consumed')
        if task!=proposal['review_packet'].get('task'): return withheld('task_changed')
        try:
            created=datetime.fromisoformat(proposal['created_at'])
            if created.tzinfo is None: return withheld('invalid_timestamp')
            age=(self.clock()-created).total_seconds()
            if not 0<=age<=self.max_age: return withheld('proposal_expired')
        except (TypeError,ValueError,KeyError): return withheld('invalid_timestamp')
        target=proposal['review_packet']['proposed']
        try: current=inspect(proposal)
        except Exception as error: return withheld('live_check_failed:'+type(error).__name__)
        if not isinstance(current,dict): return withheld('invalid_live_check')
        for key in ('authorized','routine','visible','enabled','is_button'):
            if current.get(key) is not True: return withheld('live_check_'+key)
        if current.get('requires_confirmation') is not False: return withheld('host_confirmation_required')
        if current.get('image_sha256')!=proposal.get('image_sha256') or current.get('candidate_id')!=target['id'] or current.get('task')!=task:
            return withheld('live_binding_changed')
        if str(current.get('label','')).casefold()!=target['label'].casefold(): return withheld('live_label_changed')
        # The host maps original screenshot coordinates to its own driver, checking bounds.
        if current.get('coordinates_verified') is not True: return withheld('coordinate_mapping_unverified')
        if not 0<=(self.clock()-created).total_seconds()<=self.max_age: return withheld('proposal_expired_during_live_check')
        self.consumed.add(identity)
        try:
            receipt=click(target,current)
            if receipt is False:
                return dict(status='click_outcome_unknown',reason='driver_reported_failure',attempted=True,executed_actions=None,retry_allowed=False)
        except Exception as error:
            return dict(status='click_outcome_unknown',reason=type(error).__name__,attempted=True,executed_actions=None,retry_allowed=False)
        try: checked=verify(proposal,current)
        except Exception as error:
            return dict(status='verification_failed',reason=type(error).__name__,attempted=True,executed_actions=True,retry_allowed=False)
        return dict(status='clicked_verified' if checked is True else 'verification_failed',
            attempted=True,executed_actions=True,verified=checked is True,retry_allowed=False)
