"""Read-only Tavi adapters for Codex MCP; no capture, overlay, clicks or agent launch.

This module deliberately does not import an MCP SDK. It is usable in unit tests
without a network connection, Windows session, or logged-in Codex account.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parent
MAX_TASK = 16000
MAX_SNAPSHOT_BYTES = 256_000


def status() -> dict[str, Any]:
    """Explain what is installed without asking Codex to take a screenshot."""
    configured = (ROOT / 'tavi.config.json').is_file()
    return {
        'status': 'ready' if configured else 'configuration_required',
        'config_present': configured,
        'scope': 'local_codex_tools',
        'capabilities': ['task_routing', 'host_snapshot_control_matching'],
        'can_capture_screen': False,
        'can_draw_overlay': False,
        'can_click_or_type': False,
        'can_switch_current_codex_model': False,
        'instructions': ('Copy tavi.config.example.json to tavi.config.json and set your local '
                         'skill roots and Codex model policy.' if not configured else
                         'Use route_task for advice and match_controls for fresh host-owned snapshots.'),
    }


def route_task(task: str, preference: str = 'auto') -> dict[str, Any]:
    """Ask installed Tavi for routing *advice* (never --execute or --record)."""
    if not isinstance(task, str) or not task.strip() or len(task) > MAX_TASK:
        raise ValueError('Task must contain 1–16000 characters')
    if preference not in ('auto', 'speed', 'quality'):
        raise ValueError('Preference must be auto, speed, or quality')
    if not (ROOT / 'tavi.config.json').is_file():
        return {'status': 'configuration_required', 'action_taken': False,
                'reason': 'Create tavi.config.json from tavi.config.example.json'}
    command = [sys.executable, str(ROOT / 'tavi.py'), 'route', task,
               '--preference', preference]
    try:
        completed = subprocess.run(command, cwd=ROOT, capture_output=True,
                                   text=True, encoding='utf-8', timeout=75,
                                   check=False)
    except (OSError, subprocess.TimeoutExpired):
        return {'status': 'unavailable', 'reason': 'local_router_unavailable',
                'action_taken': False}
    if completed.returncode:
        # Avoid putting arbitrary CLI diagnostics, paths or secrets in tool output.
        return {'status': 'unavailable', 'reason': 'local_router_failed',
                'action_taken': False,
                'next_step': 'Run python tavi.py doctor locally to diagnose'}
    try:
        decision = json.loads(completed.stdout)
    except (ValueError, TypeError):
        return {'status': 'unavailable', 'reason': 'invalid_router_response',
                'action_taken': False}
    if not isinstance(decision, dict) or decision.get('status') not in ('recommended', 'needs_review'):
        return {'status': 'unavailable', 'reason': 'unexpected_router_response',
                'action_taken': False}
    # Prevent the agent treating policy-based model hints as automatic switching.
    return {
        'status': decision['status'],
        'model': decision.get('model'),
        'skills': [{key: item.get(key) for key in ('name', 'path', 'selection')}
                   for item in decision.get('skills', []) if isinstance(item, dict)],
        'warnings': decision.get('warnings', []),
        'provider': decision.get('provider', 'codex'),
        'decision_id': decision.get('decision_id'),
        'advisory_only': True,
        'model_switched': False,
        'hosted_task_started': False,
        'action_taken': False,
    }


def match_controls(snapshot: dict[str, Any], queries: list[dict[str, Any]]) -> dict[str, Any]:
    """Resolve exact named controls from current host-supplied facts, no OCR.

    The caller (Codex or its trusted driver) must supply the actual latest
    snapshot; this function will never access the desktop or a browser itself.
    The returned identity is only a planner hint, never click authorization.
    """
    if not isinstance(snapshot, dict) or not isinstance(queries, list):
        raise ValueError('Expected a host snapshot object and queries list')
    if len(queries) < 1 or len(queries) > 16:
        raise ValueError('Provide 1–16 queries')
    try:
        size = len(json.dumps({'snapshot': snapshot, 'queries': queries},
                              ensure_ascii=False, allow_nan=False).encode('utf-8'))
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError('Invalid host snapshot JSON') from exc
    if size > MAX_SNAPSHOT_BYTES:
        raise ValueError('Host snapshot exceeds 256 KB')
    from tavi_observe import dispatch
    from tavi_observe_wire import planner_packet
    full = dispatch(snapshot, queries, image=None, detail='brief')
    return planner_packet(full)
