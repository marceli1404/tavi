"""Privacy-preserving, opt-in performance accounting for Tavi computer use.

Records only allowlisted stage timings, route counts, wire byte sizes and
explicit provider-reported token counts. No task strings, page content,
control names, screenshots, URLs, API keys or raw model messages are kept.
Missing usage stays unknown: never confuse zero tokens with unmeasured.
"""
from __future__ import annotations

from collections import Counter, deque
from contextlib import contextmanager
import math
import statistics
import time

STAGES = frozenset({
    'browser_dom_capture', 'dom_resolve', 'visual_fallback',
    'host_recheck', 'action', 'result_verify', 'host_model',
    'stream_request',
})
ROUTES = frozenset({
    'host_control', 'visual_review', 'needs_screenshot',
    'host_review', 'reobserve',
})


def _nonnegative(value, label, *, integer=False):
    if integer:
        if type(value) is not int or value < 0:
            raise ValueError('Invalid ' + label)
    elif type(value) not in (float, int) or not math.isfinite(value) or value < 0:
        raise ValueError('Invalid ' + label)
    return value


def _percentile(sorted_samples, pct):
    if not sorted_samples:
        return None
    # Nearest-rank percentile: stable across Python versions.
    return sorted_samples[max(0, math.ceil(len(sorted_samples)*pct)-1)]


class UsageMetrics:
    """Bounded, read-only numeric counters; instantiation never writes files."""

    def __init__(self, *, sample_limit=512):
        if type(sample_limit) is not int or not 16 <= sample_limit <= 100000:
            raise ValueError('sample_limit must be an integer from 16 to 100000')
        self.sample_limit = sample_limit
        self._samples = {stage: deque(maxlen=sample_limit) for stage in STAGES}
        self._totals = Counter()
        self._counts = Counter()
        self._providers = Counter()
        self._provider_calls = 0
        self._provider_usage_missing = 0
        self._provider_cache_missing = 0
        self._provider_cache_reported = 0

    def record_stage(self, stage, elapsed_ms):
        if stage not in STAGES:
            raise ValueError('Unsupported performance stage')
        _nonnegative(elapsed_ms, 'stage latency')
        self._samples[stage].append(round(float(elapsed_ms), 6))
        self._totals[stage] += 1

    @contextmanager
    def stage(self, stage):
        if stage not in STAGES:
            raise ValueError('Unsupported performance stage')
        started = time.perf_counter()
        try:
            yield
        finally:
            self.record_stage(stage, (time.perf_counter()-started)*1000)

    def observe(self, packet, *, wire_bytes=None):
        """Consume *only* numeric/enum fields from a verified route packet."""
        if not isinstance(packet, dict) or packet.get('format') != 'tavi-observe-route-v1':
            raise ValueError('Unsupported observation result')
        if packet.get('authorization_granted') is not False or packet.get('executed_actions') is not False:
            raise ValueError('Only non-executing observation packets can be recorded')
        counts = packet.get('counts')
        if not isinstance(counts,dict):
            raise ValueError('Missing routing counts')
        routes = packet.get('routes')
        if not isinstance(routes,list) or not 1 <= len(routes) <= 16:
            raise ValueError('Invalid routing records')
        allowed = [r['route'] for r in routes if isinstance(r,dict) and r.get('route') in ROUTES]
        if len(allowed)!=len(routes):
            raise ValueError('Unknown routing outcome')
        if counts.get('queries')!=len(routes):
            raise ValueError('Inconsistent query count')
        for name in ('image_preparations','ocr_passes'):
            _nonnegative(counts.get(name),name,integer=True)
            if counts[name]>1:
                raise ValueError('Visual work exceeded one pass')
        if wire_bytes is not None:
            _nonnegative(wire_bytes,'wire size',integer=True)
        self._counts['observations'] += 1
        self._counts['queries'] += len(routes)
        self._counts['image_preparations'] += counts['image_preparations']
        self._counts['ocr_passes'] += counts['ocr_passes']
        self._counts['response_bytes_measured'] += int(wire_bytes is not None)
        if wire_bytes is not None:
            self._counts['response_bytes_total'] += wire_bytes
        for outcome in allowed:
            self._counts['routes_'+outcome] += 1

    def provider_usage(self, *, input_tokens=None, output_tokens=None,
                       cached_input_tokens=None, elapsed_ms=None):
        """Count only usage numbers reported by a host, never infer tokens.

        No token counts should be supplied for local route-only requests.
        Provider name/model identifiers and prompts are intentionally omitted.
        """
        missing = input_tokens is None or output_tokens is None
        if missing:
            if input_tokens is not None or output_tokens is not None or cached_input_tokens is not None:
                raise ValueError('Token usage must be complete or unavailable')
        else:
            _nonnegative(input_tokens,'input_tokens',integer=True)
            _nonnegative(output_tokens,'output_tokens',integer=True)
            if cached_input_tokens is not None:
                _nonnegative(cached_input_tokens,'cached_input_tokens',integer=True)
                if cached_input_tokens>input_tokens:
                    raise ValueError('cached_input_tokens exceeds input_tokens')
        if elapsed_ms is not None:
            _nonnegative(elapsed_ms,'model latency')
        self._provider_calls += 1
        if missing:
            self._provider_usage_missing += 1
        else:
            self._providers['input_tokens'] += input_tokens
            self._providers['output_tokens'] += output_tokens
            if cached_input_tokens is None:
                self._provider_cache_missing += 1
            else:
                self._providers['cached_input_tokens'] += cached_input_tokens
                self._provider_cache_reported += 1
            self._providers['metered_calls'] += 1
        if elapsed_ms is not None:
            self.record_stage('host_model', elapsed_ms)

    def summary(self):
        timings = {}
        for stage in sorted(STAGES):
            samples = sorted(self._samples[stage])
            if not samples:
                continue
            timings[stage] = {
                'count': self._totals[stage],
                'samples_kept': len(samples),
                'median_ms': round(statistics.median(samples),3),
                'p95_ms': round(_percentile(samples,.95),3),
                'max_ms': round(samples[-1],3),
            }
        return {
            'format': 'tavi-computer-use-metrics-v1',
            'scope': 'Numeric-only timings and counts; no raw UI, prompts, actions or screenshots.',
            'counters': dict(sorted(self._counts.items())),
            'timings': timings,
            'provider_tokens': {
                'status': ('unavailable' if not self._providers['metered_calls']
                           else 'partial' if self._provider_usage_missing else 'reported'),
                'calls': self._provider_calls,
                'measured_calls': self._providers['metered_calls'],
                'unmeasured_calls': self._provider_usage_missing,
                'input': self._providers['input_tokens'] if self._providers['metered_calls'] else None,
                'output': self._providers['output_tokens'] if self._providers['metered_calls'] else None,
                'cached_input': (self._providers['cached_input_tokens']
                                 if self._provider_cache_reported and not self._provider_cache_missing else None),
                'cached_input_status': ('unavailable' if not self._provider_cache_reported
                                        else 'partial' if self._provider_cache_missing else 'reported'),
                'cached_input_measured_calls': self._provider_cache_reported,
            },
            'actual_model_tokens_measured': self._providers['metered_calls'] > 0,
            'screenshot_bytes_recorded': 0,
            'automatic_actions_authorized': False,
        }
