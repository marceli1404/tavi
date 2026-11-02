"""Optional inventory-bound semantic advice for routing; no model calls or installs."""
import copy
import json
from pathlib import Path
import sys
from tavi_coverage_review import packet,validate_review,text,digest

PACKET_BYTES=131072
CONTEXT_BYTES=1048576
OUTPUT_BYTES=2097152


def read_input(path):
    if str(path)=='-':raw=sys.stdin.buffer.read(262145)
    else:
        with Path(path).open('rb') as stream:raw=stream.read(262145)
    if len(raw)>262144:raise ValueError('Route coverage JSON exceeds256KiB')
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('Duplicate route coverage JSON field: '+key)
            result[key]=value
        return result
    return json.loads(raw.decode('utf-8-sig'),object_pairs_hook=unique)


def prepare(task,requirements,skills,excluded_skills=()):
    if not isinstance(skills,list) or len(skills)>1000:
        raise ValueError('Coverage review supports at most1000 installed descriptions')
    if not isinstance(excluded_skills,(list,tuple)) or any(not isinstance(x,str) for x in excluded_skills):
        raise ValueError('Skill exclusions must be text identifiers')
    catalog=[]
    for skill in skills:
        if not isinstance(skill,dict):raise ValueError('Inventory skills must be objects')
        catalog.append(dict(id=text(skill['id'],'Skill ID',200),name=text(skill['name'],'Skill name',200),
                            description=text(skill['description'],'Skill description',4000)))
    if len({s['id'] for s in catalog})!=len(catalog):raise ValueError('Inventory skill IDs must be unique')
    identifiers={v for s in catalog for v in (s['id'],s['name'])}
    if set(excluded_skills)-identifiers:raise ValueError('Coverage exclusions name an unavailable skill')
    excluded=sorted(s['id'] for s in catalog if s['id'] in excluded_skills or s['name'] in excluded_skills)
    eligible=sorted([s for s in catalog if s['id'] not in excluded],key=lambda s:s['id'])
    # Validate task/requirements with the established packet contract first.
    empty=packet(dict(task=task,requirements=requirements,skills=[]))
    root=dict(version='tavi-route-coverage-v1',task=task,requirements=empty['snapshot']['requirements'],
              eligible_inventory=[dict(id=s['id'],name=s['name'],description_sha256=digest(s['description'])) for s in eligible],
              excluded_skill_ids=excluded,inventory_scope='complete supplied eligible inventory')
    if len(json.dumps(root,ensure_ascii=False).encode('utf-8'))>CONTEXT_BYTES:
        raise ValueError('Route coverage context exceeds1MiB')
    base_size=len(json.dumps(empty['snapshot'],ensure_ascii=False).encode('utf-8'))
    chunks=[];chunk=[];size=base_size
    for skill in eligible:
        item=dict(id=skill['id'],description=skill['description'])
        extra=len(json.dumps(item,ensure_ascii=False).encode('utf-8'))
        if base_size+extra>PACKET_BYTES:
            raise ValueError('A skill cannot fit with the full task/requirements; narrow the explicit requirements')
        if chunk and (len(chunk)==100 or size+extra+2>PACKET_BYTES):
            chunks.append(chunk);chunk=[];size=base_size
        size+=extra+(2 if chunk else 0);chunk.append(item)
    if chunk or not chunks:chunks.append(chunk)
    packets=[packet(dict(task=task,requirements=requirements,skills=part)) for part in chunks]
    context_id=digest(root)
    result=dict(version=root['version'],context_id=context_id,status='needs_semantic_review',
                packets=packets,packet_count=len(packets),eligible_skill_count=len(eligible),
                supplied_skill_count=len(catalog),excluded_skill_ids=excluded,
                inventory_scope=root['inventory_scope'],probability=None,installation_authorized=False,
                reviewer_identity_verified=False,execution_capability_verified=False,
                review_grants_execution_authority=False,
                native_operation_rule='List requirements handled directly without an installed skill in native_requirement_ids; leave their skill_ids empty in every packet. This is advice, not verified capability.',
                answer_format=dict(context_id=context_id,native_requirement_ids=[],reviews=[dict(packet_id=p['packet_id'],coverage=[
                    dict(requirement_id=r['id'],skill_ids=[]) for r in p['snapshot']['requirements']]) for p in packets]))
    if len(json.dumps(result,ensure_ascii=False).encode('utf-8'))>OUTPUT_BYTES:
        raise ValueError('Route coverage packet collection exceeds2MiB')
    return result


def resolve(task,requirements,skills,answer,excluded_skills=()):
    current=prepare(task,requirements,skills,excluded_skills)
    if not isinstance(answer,dict) or set(answer) not in ({'context_id','reviews'},{'context_id','reviews','native_requirement_ids'}):
        raise ValueError('Coverage answer requires context_id and reviews, with optional native_requirement_ids')
    if answer['context_id']!=current['context_id']:
        raise ValueError('Coverage answer is stale for the current task, requirements, inventory or exclusions')
    reviews=answer['reviews']
    if not isinstance(reviews,list) or any(not isinstance(r,dict) or set(r)!={'packet_id','coverage'}
                                         or not isinstance(r['packet_id'],str) for r in reviews):
        raise ValueError('Coverage reviews require packet_id and coverage objects')
    ids=[r['packet_id'] for r in reviews];expected={p['packet_id'] for p in current['packets']}
    if len(set(ids))!=len(ids) or set(ids)!=expected:
        raise ValueError('Coverage answer must review every current packet exactly once')
    by_id={r['packet_id']:r for r in reviews}
    requirements_rows=current['packets'][0]['snapshot']['requirements']
    native=answer.get('native_requirement_ids',[])
    requirement_ids={r['id'] for r in requirements_rows}
    if not isinstance(native,list) or any(not isinstance(r,str) for r in native) or len(native)!=len(set(native)) or not set(native)<=requirement_ids:
        raise ValueError('Native operation claims require unique current requirement IDs')
    supporting={r['id']:set() for r in requirements_rows}
    for p in current['packets']:
        validated=validate_review(p,by_id[p['packet_id']])
        for row in validated['coverage']:supporting[row['requirement_id']].update(row['skill_ids'])
    if any(supporting[r] for r in native):raise ValueError('Choose either direct host handling or supporting skills for each requirement')
    coverage=[dict(requirement_id=r['id'],skill_ids=sorted(supporting[r['id']]),handled_without_skill=r['id'] in native) for r in requirements_rows]
    missing=[r['requirement_id'] for r in coverage if not r['skill_ids'] and not r['handled_without_skill']]
    return dict(version=current['version'],context_id=current['context_id'],status='provided_semantic_review',
                coverage=coverage,missing_requirement_ids=missing,supporting_skill_ids=sorted(set().union(*supporting.values())),
                discovery_suggested=bool(missing),packets_reviewed=len(reviews),eligible_skill_count=current['eligible_skill_count'],
                native_requirement_ids=sorted(native),native_capability_verified=False,
                excluded_skill_ids=current['excluded_skill_ids'],inventory_scope=current['inventory_scope'],
                probability=None,reviewer_identity_verified=False,execution_capability_verified=False,
                installation_authorized=False,review_grants_execution_authority=False,
                scope='Provided skill-description coverage and direct-host advice, not verified behaviour, entitlement or calibrated success.')


def attach(decision,task,requirements,skills,answer=None,excluded_skills=()):
    result=copy.deepcopy(decision)
    base_discovery=copy.deepcopy(result['discovery'])
    if answer is None:
        current=prepare(task,requirements,skills,excluded_skills)
        result['capability_review']=dict(current,base_discovery=base_discovery)
        result['skills']=[s for s in result['skills'] if s['selection'] in ('explicit','required-policy')]
        result['explanation']['learned_skills']=[]
        result['explanation']['reviewed_skills']=[]
        result['status']='needs_review'
        result['discovery']=dict(status='needs_capability_review',score=None,installation_authorized=False,
                                 source='requested_inventory_coverage_review')
        result['warnings'].append('Requested capability review is pending; the local score does not establish inventory coverage.')
    else:
        reviewed=resolve(task,requirements,skills,answer,excluded_skills)
        result['capability_review']=dict(reviewed,base_discovery=base_discovery)
        catalog={s['id']:s for s in skills}
        kept=[s for s in result['skills'] if s['selection'] in ('explicit','required-policy')]
        existing={s['id'] for s in kept}
        for ident in reviewed['supporting_skill_ids']:
            if ident not in existing:kept.append(dict(**catalog[ident],selection='coverage-review',score=None));existing.add(ident)
        result['skills']=kept
        result['discovery']=dict(status='search_recommended' if reviewed['discovery_suggested'] else 'not_needed',
                                 score=None,installation_authorized=False,source='provided_inventory_coverage_review',
                                 missing_requirement_ids=reviewed['missing_requirement_ids'])
        if reviewed['discovery_suggested']:
            from tavi_awesomeskill import search_url
            result['status']='needs_review'
            result['discovery'].update(provider='awesomeskill',source_selection='user-preference-policy',
                suggested_query=task[:160],search_url=search_url(task[:160]),
                next_step='Review the uncovered operations and pinned upstream source before recommending any download.')
        result['explanation']['learned_skills']=[]
        result['explanation']['reviewed_skills']=[s['name'] for s in kept if s['selection']=='coverage-review']
        result['warnings'].append('Provided coverage review is advisory; skill behaviour and reviewer identity are not verified.')
    result['routing_evidence']['capability_review_requested']=True
    result['routing_evidence']['changes_routing']=True
    result['routing_evidence']['model_tier_changed_by_coverage_review']=False
    return result
