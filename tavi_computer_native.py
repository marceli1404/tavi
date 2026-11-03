"""Read-only, foreground-only Windows UI Automation bridge for Computer hosts.

This does NOT implement Computer, clicks, screenshots, typing, navigation,
or permission decisions. It suggests exact native controls; Computer remains
responsible for viewing the app, validating the live element, authorising an
action and verifying the result. No UI text is sent to any network service.

The Windows PowerShell UIA collector stays warm across JSON-line requests.
Windows-only observation is strictly opt-in; unit tests inject a fake capture.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
from queue import Empty, Queue
import subprocess
import sys
from threading import Lock, Thread
import time
from uuid import uuid4

from tavi_controls import ControlIndex, ROLES
from tavi_observe import dispatch
from tavi_observe_wire import planner_packet

MAX_LINE = 4096
MAX_NATIVE_RESPONSE = 2_000_000
SUPPORTED = frozenset({'button', 'link', 'tab', 'checkbox', 'switch',
                       'radio', 'menuitem', 'textbox', 'combobox'})


def _unique_pairs(pairs):
    output = {}
    for key, value in pairs:
        if key in output:
            raise ValueError('Duplicate JSON property')
        output[key] = value
    return output


def _decode(raw):
    if not isinstance(raw, str) or len(raw.encode('utf-8')) > MAX_NATIVE_RESPONSE:
        raise ValueError('Native collector returned an oversized response')
    value = json.loads(raw, object_pairs_hook=_unique_pairs,
                       parse_constant=lambda _: (_ for _ in ()).throw(
                           ValueError('Non-finite native value')))
    if not isinstance(value, dict):
        raise ValueError('Invalid native collector response')
    return value


def _binding(data):
    if not isinstance(data, dict) or set(data) != {'hwnd', 'process_id', 'rect'}:
        raise ValueError('Untrusted native window binding')
    hwnd, pid, rect = data['hwnd'], data['process_id'], data['rect']
    if (type(hwnd) is not int or hwnd <= 0 or type(pid) is not int or pid <= 0
            or not isinstance(rect, list) or len(rect) != 4
            or any(type(v) is not int or abs(v) > 32768 for v in rect)
            or not (0 < rect[2] <= 16384 and 0 < rect[3] <= 16384)):
        raise ValueError('Invalid native window identity or geometry')
    return dict(hwnd=hwnd, process_id=pid, rect=list(rect))


def _candidate(identity):
    if not isinstance(identity, list) or len(identity) != 5:
        raise ValueError('Expected exact projected control identity')
    ident, label, role, context, bounds = identity
    if (not isinstance(ident, str) or not ident.startswith('uia-')
            or not isinstance(label, str) or not label.strip()
            or not isinstance(role, str) or role not in ROLES
            or not isinstance(context, str)
            or not isinstance(bounds, list) or len(bounds) != 4
            or any(type(v) not in (int, float) or not math.isfinite(v)
                   for v in bounds) or bounds[2] <= 0 or bounds[3] <= 0):
        raise ValueError('Invalid native control identity')
    return identity


def _query(request):
    if not isinstance(request, dict):
        raise ValueError('Expected request object')
    if request.get('op') not in ('suggest', 'recheck'):
        raise ValueError('Only suggest and recheck are supported')
    allowed = {'id', 'op', 'target', 'role', 'context'}
    if request['op'] == 'recheck':
        allowed |= {'expected'}
    if set(request) - allowed:
        raise ValueError('Unsupported fields; no action commands')
    target = request.get('target')
    role = request.get('role', 'button')
    context = request.get('context')
    ident = request.get('id')
    if (not isinstance(target, str) or not target.strip()
            or len(target) > 128 or role not in SUPPORTED
            or context is not None and (not isinstance(context, str)
                                        or not context.strip() or len(context) > 128)):
        raise ValueError('Invalid scoped control query')
    if ident is not None and (not isinstance(ident, str) or
                              not ident.strip() or len(ident) > 80):
        raise ValueError('Invalid request identity')
    if request['op'] == 'recheck':
        expected = request.get('expected')
        if not isinstance(expected, dict) or set(expected) != {'window_binding', 'candidate'}:
            raise ValueError('Recheck requires exact original binding and candidate')
        _binding(expected['window_binding'])
        _candidate(expected['candidate'])
    return request


class WindowsUiaWorker:
    """Persistent, synchronous Windows PowerShell worker; never a click driver."""

    def __init__(self, *, executable='powershell.exe', script=None, timeout_seconds=8):
        if sys.platform != 'win32':
            raise RuntimeError('Native UIA capture requires an interactive Windows desktop')
        script = Path(script) if script is not None else Path(__file__).with_name('tavi_native_uia.ps1')
        if not script.is_file():
            raise RuntimeError('Bundled read-only UIA worker unavailable')
        if not 1 <= timeout_seconds <= 20:
            raise ValueError('Invalid worker timeout')
        self._lock = Lock()
        self._messages = Queue(maxsize=2)
        self._timeout = timeout_seconds
        # File argument is literal, not shell-interpreted. The worker does
        # not accept PowerShell expressions or execution arguments from tasks.
        self._process = subprocess.Popen(
            [executable, '-NoLogo', '-NoProfile', '-NonInteractive',
             '-ExecutionPolicy', 'Bypass', '-File', str(script)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding='utf-8',
            errors='strict', bufsize=1, shell=False)
        self._reader = Thread(target=self._read, daemon=True)
        self._reader.start()

    def _read(self):
        try:
            for line in self._process.stdout:
                # Never buffer unlimited UI text from an untrusted provider.
                if len(line.encode('utf-8')) > MAX_NATIVE_RESPONSE:
                    self._messages.put({'status': 'error'})
                    break
                self._messages.put(line)
        except Exception:
            pass
        finally:
            try:
                self._messages.put_nowait(None)
            except Exception:
                pass

    def capture(self):
        with self._lock:
            if self._process.poll() is not None:
                raise RuntimeError('Native UIA worker exited')
            try:
                self._process.stdin.write('{"op":"capture"}\n')
                self._process.stdin.flush()
                response = self._messages.get(timeout=self._timeout)
                result = _decode(response) if isinstance(response, str) else response
                if not isinstance(result, dict) or result.get('status') != 'captured':
                    raise RuntimeError('Native UIA observation unavailable')
                return result
            except (Empty, OSError, ValueError, TypeError, RuntimeError):
                self.close()
                raise RuntimeError('Native UIA observation unavailable') from None

    def close(self):
        process = getattr(self, '_process', None)
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class NativeComputerAdapter:
    """Scoped, fresh candidate proposals; never grants or performs an action."""

    def __init__(self, provider):
        if not callable(getattr(provider, 'capture', None)):
            raise ValueError('Expected trusted read-only native provider')
        self.provider = provider

    def _observe(self, request):
        started = time.perf_counter()
        captured_at = datetime.now(timezone.utc).isoformat()
        raw = self.provider.capture()
        if not isinstance(raw, dict) or raw.get('status') != 'captured':
            raise ValueError('Native capture unavailable')
        binding = _binding(raw.get('window_binding'))
        if (set(raw) != {'status', 'window_binding', 'viewport', 'controls', 'visited_nodes'}
                or raw.get('viewport') != binding['rect'][2:]
                or type(raw.get('visited_nodes')) is not int
                or not 1 <= raw['visited_nodes'] <= 1600
                or not isinstance(raw.get('controls'), list)
                or len(raw['controls']) > 1600):
            raise ValueError('Native inventory failed size or provenance checks')
        snapshot = dict(
            format='tavi-control-snapshot-v1',
            snapshot_id=uuid4().hex,
            captured_at=captured_at,
            source='supported_native',
            viewport=raw['viewport'],
            controls=raw['controls'])
        ControlIndex(snapshot)  # full validation before routing
        query = dict(id=request.get('id') or 'native', task='Inspect requested native control',
                     target=request['target'], role=request.get('role','button'))
        if request.get('context') is not None:
            query['context'] = request['context']
        result = planner_packet(dispatch(snapshot, [query]))
        result['window_binding'] = binding
        result['elapsed_observation_ms'] = round((time.perf_counter()-started)*1000, 3)
        result['hosted_model_calls'] = 0
        result['requires_host_recheck_before_action'] = True
        result['fallback'] = ('computer_screenshot'
                              if result['rows'][0][1] == 'needs_screenshot' else None)
        return result

    def handle(self, request):
        _query(request)
        view = self._observe(request)
        if request['op'] == 'suggest':
            return view
        expected = request['expected']
        row = view['rows'][0]
        match = bool(
            row[1] == 'host_control' and
            view['window_binding'] == expected['window_binding'] and
            row[3] == expected['candidate'])
        # Recheck result is advisory, not a capability token. Computer must
        # still inspect the current app and authorise each action itself.
        return dict(
            format='tavi-native-recheck-v1',
            request_id=request.get('id'),
            window_binding=view['window_binding'],
            snapshot_sha256=view['snapshot_sha256'],
            route=row[1], reason=row[2],
            exact_candidate_unchanged=match,
            requires_live_host_check=True,
            authorization_granted=False,
            executed_actions=False,
            planner_only=True,
            elapsed_observation_ms=view['elapsed_observation_ms'])


def serve(input_stream=None, output_stream=None, *, provider=None):
    input_stream = sys.stdin if input_stream is None else input_stream
    output_stream = sys.stdout if output_stream is None else output_stream
    local_provider = provider is None
    if local_provider:
        provider = WindowsUiaWorker()
    adapter = NativeComputerAdapter(provider)
    def emit(value):
        output_stream.write(json.dumps(value, ensure_ascii=False, allow_nan=False,
                                       separators=(',',':'))+'\n')
        output_stream.flush()
    emit(dict(format='tavi-computer-native-v1', status='ready',
              methods=['suggest','recheck'], read_only=True,
              action_authorized=False))
    try:
        for line in input_stream:
            if len(line.encode('utf-8')) > MAX_LINE:
                emit(dict(status='error',reason='invalid_request',
                          authorization_granted=False,executed_actions=False))
                continue
            try:
                request = _decode(line)
                response = adapter.handle(request)
                response['status'] = 'observed'
                emit(response)
            except (ValueError, TypeError):
                emit(dict(status='error',reason='invalid_request',
                          authorization_granted=False,executed_actions=False))
            except (RuntimeError, OSError):
                emit(dict(status='unavailable',reason='native_observation_unavailable',
                          fallback='computer_screenshot',requires_live_host_check=True,
                          authorization_granted=False,executed_actions=False))
    finally:
        if local_provider:
            provider.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(serve())
