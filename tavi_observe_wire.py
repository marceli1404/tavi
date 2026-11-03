"""Minimal, *non-authoritative* planner projection for fresh Tavi observations.

This is deliberately lossy: detailed evidence remains inside the trusted
host, and a model must never use a projected row to execute an action.
No cross-request caching, reconstructed snapshot, hidden permission change,
image capture, model call or browser action happens here.
"""
from __future__ import annotations

import math

FORMAT = 'tavi-observe-planner-v1'
COLUMNS = ('query_id', 'route', 'reason', 'candidate', 'visual')
ROUTE_REASONS = {
    'host_control': ('unique_exact_control',),
    'needs_screenshot': ('no_exact_control',),
    'visual_review': ('no_exact_control_visual_evidence',),
    'host_review': ('ambiguous_control', 'control_unavailable'),
    'reobserve': ('stale_snapshot', 'future_snapshot'),
}
CONTROL_REASONS = {
    'host_control': ('unique_exact_control',),
    'needs_screenshot': ('no_exact_control',),
    'visual_review': ('no_exact_control',),
    'host_review': ('ambiguous_control', 'control_unavailable'),
    'reobserve': ('stale_snapshot', 'future_snapshot'),
}
SAFETY_FLAGS = (
    'requires_live_host_check', 'requires_fresh_observation_after_action',
)
DENIAL_FLAGS = (
    'authorization_granted', 'executed_actions', 'action_sequence_authorized',
)


def _no_authority(value, *, extra=()):
    if not isinstance(value, dict):
        raise ValueError('Expected read-only control evidence')
    if value.get('requires_live_host_check') is not True:
        raise ValueError('Live host check is mandatory')
    if any(value.get(flag) is not False for flag in
           ('authorization_granted', 'executed_actions', *extra)):
        raise ValueError('Planner evidence may never authorize actions')


def _candidate(candidate):
    if not isinstance(candidate, dict) or set(candidate) != {
        'id', 'label', 'role', 'context', 'bounds'
    }:
        raise ValueError('Invalid exact control candidate')
    if (not all(isinstance(candidate[k], str) for k in
                ('id', 'label', 'role', 'context'))
            or not candidate['id'] or not candidate['label']):
        raise ValueError('Invalid candidate control identity')
    bounds = candidate['bounds']
    if (not isinstance(bounds, list) or len(bounds) != 4 or
            any(type(v) not in (int, float) or not math.isfinite(v)
                for v in bounds) or bounds[2] <= 0 or bounds[3] <= 0):
        raise ValueError('Invalid control geometry')
    # Arrays eliminate repeated field names across many controls. Do not
    # truncate candidate identity: the host must revalidate live control.
    return [candidate[k] for k in ('id', 'label', 'role', 'context', 'bounds')]


def _visual(visual):
    if not isinstance(visual, dict):
        raise ValueError('Missing visual review')
    if 'review_packet' in visual:
        # Full local OCR proposals have no standalone requires_live_host_check
        # field; that mandatory condition is enforced on the enclosing route.
        if (visual.get('executed_actions') is not False
                or visual.get('hosted_calls') != 0
                or not isinstance(visual.get('confidence'), dict)
                or visual['confidence'].get('automatic_probability_qualified') is not False):
            raise ValueError('Full visual evidence may not execute or qualify actions')
    else:
        _no_authority(visual)
        if visual.get('automatic_probability_qualified') is not False:
            raise ValueError('Visual evidence must not qualify actions')
    packet = visual.get('review_packet') if 'review_packet' in visual else visual
    if not isinstance(packet, dict):
        raise ValueError('Invalid visual review packet')
    for field in ('proposal_id', 'image_sha256'):
        if not isinstance(visual.get(field), str) or not visual[field]:
            raise ValueError('Visual review binding missing')
    if (not isinstance(packet.get('alternatives'), list)
            or not isinstance(visual.get('review_reasons'), list)):
        raise ValueError('Missing visual review evidence')
    return {
        'proposal_id': visual['proposal_id'],
        'image_sha256': visual['image_sha256'],
        'proposed': packet.get('proposed'),
        'alternatives': packet['alternatives'],
        'review_reasons': visual['review_reasons'],
        'automatic_probability_qualified': False,
    }


def planner_packet(packet):
    """Create the compact *planner-only* view of a validated Tavi result.

    No cached or projected row may be used as a live control authority.
    Original full packet stays in the host for audit and reconciliation.
    """
    if not isinstance(packet, dict) or packet.get('format') != 'tavi-observe-route-v1':
        raise ValueError('Expected a full Tavi observation packet')
    _no_authority(packet, extra=('action_sequence_authorized',))
    if (packet.get('requires_fresh_observation_after_action') is not True
            or packet.get('policy') != 'deterministic_dom_first_v1_not_trained'
            or packet.get('hosted_calls') != 0):
        raise ValueError('Invalid observation provenance or policy')
    digest = packet.get('snapshot_sha256')
    if (not isinstance(digest, str) or len(digest) != 64
            or any(char not in '0123456789abcdef' for char in digest)):
        raise ValueError('Invalid observation digest')
    routes = packet.get('routes')
    if not isinstance(routes, list) or not 1 <= len(routes) <= 16:
        raise ValueError('Expected 1–16 fresh routes')
    counts = packet.get('counts')
    if not isinstance(counts, dict) or counts.get('queries') != len(routes):
        raise ValueError('Invalid observation counts')
    rows = []
    for item in routes:
        if not isinstance(item, dict):
            raise ValueError('Malformed observation route')
        route = item.get('route')
        reason = item.get('reason')
        if route not in ROUTE_REASONS or reason not in ROUTE_REASONS[route]:
            raise ValueError('Unsafe or unsupported observation route')
        control = item.get('control')
        _no_authority(control)
        if (control.get('reason') not in CONTROL_REASONS[route]
                or control.get('offline') is not False):
            raise ValueError('Untrusted or offline control decision')
        query_id = item.get('query_id')
        if query_id is not None and (not isinstance(query_id, str)
                                      or not query_id.strip()):
            raise ValueError('Invalid query identity')
        if route == 'host_control':
            candidate = _candidate(control.get('candidate'))
            if item.get('visual') is not None:
                raise ValueError('Unexpected visual evidence on exact control')
        else:
            candidate = None
            if control.get('candidate') is not None:
                raise ValueError('Non-exact control has unexpected candidate')
        if route == 'visual_review':
            visual = _visual(item.get('visual'))
        else:
            visual = None
            if item.get('visual') is not None:
                raise ValueError('Unexpected visual evidence')
        rows.append([query_id, route, reason, candidate, visual])

    view = {
        'format': FORMAT,
        'snapshot_sha256': digest,
        'columns': list(COLUMNS),
        'rows': rows,
        'planner_only': True,
        'requires_live_host_check': True,
        'requires_fresh_observation_after_action': True,
        'authorization_granted': False,
        'executed_actions': False,
        'action_sequence_authorized': False,
    }
    if packet.get('status') == 'routed':
        view['status'] = 'routed'
        view['request_id'] = packet.get('request_id')
    return view
