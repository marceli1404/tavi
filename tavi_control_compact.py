"""Lossless response factoring; no observation caching, inference or actions."""
from copy import deepcopy

SHARED = ('format', 'source', 'snapshot_id', 'snapshot_sha256', 'probability',
          'probability_note', 'requires_live_host_check', 'authorization_granted',
          'executed_actions', 'offline')


def compact_batch(batch):
    """Each proposal expands as {**shared_proposal_fields, **proposal}."""
    if batch.get('format') != 'tavi-control-batch-v1' or not batch.get('proposals'):
        raise ValueError('Expected a resolved control batch')
    for result in [batch, *batch['proposals']]:
        if (result.get('requires_live_host_check') is not True or
                result.get('authorization_granted') is not False or
                result.get('executed_actions') is not False):
            raise ValueError('Control response must preserve live verification and authority flags')
    result = deepcopy(batch)
    proposals = result['proposals']
    shared = {key: proposals[0][key] for key in SHARED
              if key in proposals[0] and all(key in p and p[key] == proposals[0][key] for p in proposals)}
    for proposal in proposals:
        for key in shared:
            del proposal[key]
    result['shared_proposal_fields'] = shared
    result['format'] = 'tavi-control-batch-compact-v1'
    return result
