"""Columnar, lossless JSON wire format for repeated control proposals.

This is a presentation transform only. It never captures the UI, grants
authority, executes an action, caches an observation or infers probability.
"""
from copy import deepcopy
from tavi_control_compact import compact_batch

# The resolver always emits these keys. query_id is the sole optional column.
COLUMNS = ('task_sha256', 'target', 'role', 'context', 'age_seconds',
           'candidate', 'status', 'reason', 'query_id')
REQUIRED = set(COLUMNS) - {'query_id'}


def matrix_batch(batch):
    """Factor repeated JSON keys without changing any proposal or permission."""
    compact = compact_batch(batch)  # checks authority flags and deep-copies input
    shared = compact['shared_proposal_fields']
    rows = []
    for proposal in compact['proposals']:
        if not REQUIRED <= set(proposal) or set(proposal) - set(COLUMNS):
            raise ValueError('Unexpected control proposal schema')
        if 'query_id' in proposal and proposal['query_id'] is None:
            raise ValueError('Null query ID cannot be represented losslessly')
        rows.append([proposal.get(name) for name in COLUMNS])
    return dict(format='tavi-control-matrix-v1',
                snapshot_sha256=compact['snapshot_sha256'],
                requires_live_host_check=compact['requires_live_host_check'],
                authorization_granted=compact['authorization_granted'],
                executed_actions=compact['executed_actions'],
                shared_proposal_fields=shared,
                columns=list(COLUMNS), rows=rows)


def expand_matrix(matrix):
    """Reconstruct the exact v1 batch for clients that require the full schema."""
    if not isinstance(matrix, dict) or matrix.get('format') != 'tavi-control-matrix-v1':
        raise ValueError('Unsupported control matrix')
    if matrix.get('columns') != list(COLUMNS):
        raise ValueError('Unexpected control matrix columns')
    if (matrix.get('requires_live_host_check') is not True or
            matrix.get('authorization_granted') is not False or
            matrix.get('executed_actions') is not False):
        raise ValueError('Control matrix cannot confer action authority')
    shared = matrix.get('shared_proposal_fields')
    rows = matrix.get('rows')
    if not isinstance(shared, dict) or not isinstance(rows, list) or not rows:
        raise ValueError('Invalid control matrix')
    for key, value in (('requires_live_host_check', True),
                       ('authorization_granted', False), ('executed_actions', False)):
        if shared.get(key) is not value:
            raise ValueError('Control matrix must preserve proposal authority flags')
    proposals = []
    for row in rows:
        if not isinstance(row, list) or len(row) != len(COLUMNS):
            raise ValueError('Invalid control matrix row')
        fields = dict(zip(COLUMNS, deepcopy(row)))
        if fields['query_id'] is None:
            del fields['query_id']
        proposals.append(dict(deepcopy(shared), **fields))
    batch = dict(format='tavi-control-batch-v1',
                 snapshot_sha256=matrix['snapshot_sha256'], proposals=proposals,
                 requires_live_host_check=True, authorization_granted=False,
                 executed_actions=False)
    # The same safety and schema checks apply to reconstructed proposals.
    compact_batch(batch)
    return batch
