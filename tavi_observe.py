"""DOM/accessibility-first routing for *host-provided* computer-use observations.

No browser driver, screenshot capture, hosted model, click, learned action
policy, persistent cache or permission backend is included. A fresh complete
supported-host observation is required for EVERY request, and the host must
verify live control identity and authorization before taking ANY action.
"""
from __future__ import annotations

import time
from tavi_controls import resolve_many

FORMAT = 'tavi-observe-route-v1'
VISUAL_ROLES = frozenset({'button', 'link', 'tab', 'menuitem'})
VISUAL_REASONS = frozenset({'no_exact_control'})
SAFE_REASONS = frozenset({'stale_snapshot', 'future_snapshot'})


def _validate_image(image, snapshot):
    if image is None:
        return None
    if (not isinstance(image, dict) or set(image) != {'path', 'snapshot_id'}
            or not isinstance(image['path'], str)
            or not image['path'].strip() or len(image['path']) > 4096
            or not isinstance(image['snapshot_id'], str)
            or image['snapshot_id'] != snapshot.get('snapshot_id')):
        raise ValueError('Image requires path and matching observation snapshot_id')
    # The matching ID is a *host-provided claim*, not cryptographic proof
    # that DOM and pixels came from the same live interface.
    return image['path']


def _brief_visual(proposal):
    """Small, review-only projection. Full evidence is opt-in."""
    packet = proposal['review_packet']
    confidence = proposal['confidence']
    return {
        'status': proposal['status'],
        'proposal_id': proposal['proposal_id'],
        'image_sha256': proposal['image_sha256'],
        'requested_label': packet['requested_label'],
        'proposed': packet['proposed'],
        'alternatives': packet['alternatives'],
        'review_reasons': proposal['review_reasons'],
        'confidence_percent_synthetic_only': confidence['percent'],
        'probability_status': confidence['status'],
        'automatic_probability_qualified': confidence['automatic_probability_qualified'],
        'coordinate_space': proposal['coordinate_space'],
        'image': {
            'original_size': proposal['image']['original_size'],
            'prepared_size': proposal['image']['prepared_size'],
        },
        'requires_live_host_check': True,
        'authorization_granted': False,
        'executed_actions': False,
    }


def dispatch(snapshot, queries, *, image=None, ocr_fn=None, max_edge=1600,
             detail='brief', now=None):
    """Resolve current controls first; OCR only absent supported-host text.

    For ambiguous, disabled, stale or future controls we do NOT bypass the
    accessibility/DOM warning using pixel matches. OCR never upgrades
    permissions or turns a proposal into an actionable click.
    """
    if not isinstance(snapshot, dict):
        raise ValueError('Host control snapshot must be an object')
    if not isinstance(queries, list) or not 1 <= len(queries) <= 16:
        raise ValueError('Provide 1–16 independent host control queries')
    if type(detail) is not str or detail not in ('brief', 'full'):
        raise ValueError('detail must be brief or full')
    if type(max_edge) is not int or not 512 <= max_edge <= 2600:
        raise ValueError('max_edge must be an integer from 512–2600')

    started = time.perf_counter()
    path = _validate_image(image, snapshot)
    facts = resolve_many(snapshot, queries, now=now)
    routes = []
    fallback = []
    for index, (query, proposal) in enumerate(zip(queries, facts['proposals'])):
        reason = proposal['reason']
        route = {
            'query_id': query.get('id'),
            'task_sha256': proposal['task_sha256'],
            'target': proposal['target'],
            'role': proposal['role'],
            'context': proposal['context'],
            'control': proposal,
            'visual': None,
            'route': 'host_review',
            'reason': reason,
        }
        if reason == 'unique_exact_control':
            route['route'] = 'host_control'
        elif reason in VISUAL_REASONS and proposal['role'] in VISUAL_ROLES:
            if path is None:
                route['route'] = 'needs_screenshot'
            else:
                # OCR cannot prove role or enabled state; it is a separate
                # *review* of an absent exact host-control label only.
                route['route'] = 'visual_review_pending'
                fallback.append((index, query))
        elif reason in SAFE_REASONS:
            route['route'] = 'reobserve'
        routes.append(route)

    image_preparations = ocr_passes = 0
    if fallback:
        from tavi_compact import propose_batch
        targets = [{'id': str(index), 'task': q['task'], 'target': q['target']}
                   for index, q in fallback]
        # This calls OCR exactly once, even for multiple missing targets.
        visual_batch = propose_batch(path, targets, max_edge=max_edge, ocr_fn=ocr_fn)
        if (visual_batch['image_preparations'] != 1
                or visual_batch['ocr_passes'] != 1
                or len(visual_batch['proposals']) != len(fallback)
                or visual_batch['authorization_granted']
                or visual_batch['executed_actions']):
            raise RuntimeError('Visual batch violated safe observation contract')
        image_preparations, ocr_passes = 1, 1
        for (index, _), visual in zip(fallback, visual_batch['proposals']):
            routes[index]['route'] = 'visual_review'
            routes[index]['visual'] = visual if detail == 'full' else _brief_visual(visual)
            routes[index]['reason'] = 'no_exact_control_visual_evidence'
    return {
        'format': FORMAT,
        'snapshot_sha256': facts['snapshot_sha256'],
        'routes': routes,
        'counts': {
            'queries': len(queries),
            'exact_host_controls': sum(r['route'] == 'host_control' for r in routes),
            'visual_review': sum(r['route'] == 'visual_review' for r in routes),
            'needs_screenshot': sum(r['route'] == 'needs_screenshot' for r in routes),
            'host_review_or_reobserve': sum(r['route'] in ('host_review','reobserve') for r in routes),
            'image_preparations': image_preparations,
            'ocr_passes': ocr_passes,
        },
        'policy': 'deterministic_dom_first_v1_not_trained',
        'image_binding_is_host_claim_only': True,
        'requires_fresh_observation_after_action': True,
        'requires_live_host_check': True,
        'action_sequence_authorized': False,
        'authorization_granted': False,
        'executed_actions': False,
        'hosted_calls': 0,
        'elapsed_ms': round((time.perf_counter()-started)*1000, 3),
    }
