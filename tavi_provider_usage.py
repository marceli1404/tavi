"""Strict provider-reported token usage adapter, with no API calls or payload logs.

Supported verified response shapes:
- OpenAI Responses API: usage.input_tokens/output_tokens; input_tokens_details.cached_tokens.
- OpenAI Chat Completions: usage.prompt_tokens/completion_tokens; prompt_tokens_details.cached_tokens.
Missing or incomplete usage is recorded as *unmeasured* and never inferred
from text length or JSON byte count. The response itself is never retained.
"""
from __future__ import annotations

FORMATS = frozenset({'openai_responses','openai_chat_completions'})


def _mapping(value):
    # SDK models commonly provide model_dump; do not inspect message/content.
    if isinstance(value,dict):
        return value
    if hasattr(value,'model_dump'):
        value=value.model_dump(exclude_none=True)
        if isinstance(value,dict):
            return value
    raise ValueError('Expected a response object or SDK model')


def extract(provider,response):
    if provider not in FORMATS:
        raise ValueError('Unsupported provider usage format')
    response=_mapping(response)
    usage=response.get('usage')
    if usage is None:
        return None
    if not isinstance(usage,dict):
        raise ValueError('Usage must be an object')
    if provider=='openai_responses':
        ik,ok,detail='input_tokens','output_tokens','input_tokens_details'
    else:
        ik,ok,detail='prompt_tokens','completion_tokens','prompt_tokens_details'
    incoming=usage.get(ik)
    outgoing=usage.get(ok)
    if incoming is None and outgoing is None:
        return None
    if type(incoming) is not int or incoming<0 or type(outgoing) is not int or outgoing<0:
        raise ValueError('Partial or invalid token accounting')
    total=usage.get('total_tokens')
    if total is not None and (type(total) is not int or total!=incoming+outgoing):
        raise ValueError('Provider total does not match reported input and output')
    breakdown=usage.get(detail)
    cached=None
    if breakdown is not None:
        if not isinstance(breakdown,dict):
            raise ValueError('Invalid cache usage breakdown')
        cached=breakdown.get('cached_tokens')
        if cached is not None and (type(cached) is not int or not 0<=cached<=incoming):
            raise ValueError('Invalid provider cached token count')
    return dict(input_tokens=incoming,output_tokens=outgoing,cached_input_tokens=cached)


def record(metrics,provider,response,*,elapsed_ms=None):
    """Consume numeric usage from a response; never store response text."""
    values=extract(provider,response)
    metrics.provider_usage(**(values or {}),elapsed_ms=elapsed_ms)
    return values is not None
