"""Lazily started local computer-use observation routing.

Accepts independent JSON-line snapshots from a supported trusted host. An
OCR subprocess is created only on an actual DOM miss with an image. This
stream does not capture, click, use network APIs or execute model output.
"""
import json
import sys
import time
from collections import deque

from tavi_observe import dispatch
from tavi_ocr import OcrSession

MAX_REQUEST_BYTES = 2_000_000


def _object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Duplicate JSON field')
        value[key] = item
    return value


def run(input_stream=None, output_stream=None, session_factory=OcrSession, metrics=None):
    input_stream = sys.stdin if input_stream is None else input_stream
    output_stream = sys.stdout if output_stream is None else output_stream
    for stream in (input_stream, output_stream):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')

    def emit(payload):
        output_stream.write(json.dumps(payload, ensure_ascii=False,
                                      allow_nan=False, separators=(',', ':'))+'\n')
        output_stream.flush()

    session = None
    recent_ids = set()
    recent_order = deque()

    def local_ocr(image):
        nonlocal session
        if session is None:
            session = session_factory()
        return session(image)

    emit(dict(status='ready', format='tavi-observe-stream-v1',
              policy='deterministic_dom_first_v1_not_trained',
              requires_live_host_check=True,
              authorization_granted=False, executed_actions=False))
    try:
        while True:
            line = input_stream.readline(MAX_REQUEST_BYTES + 1)
            if not line:
                break
            if len(line) > MAX_REQUEST_BYTES or len(line.encode('utf-8')) > MAX_REQUEST_BYTES:
                emit(dict(status='error', error='Observation request exceeds 2MB',
                          authorization_granted=False, executed_actions=False))
                return 1
            request_id = None
            try:
                request = json.loads(line, object_pairs_hook=_object,
                    parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Non-finite JSON value')))
                if not isinstance(request, dict) or not {'snapshot', 'queries'} <= set(request):
                    raise ValueError('Expected snapshot and queries')
                if set(request) - {'id','snapshot','queries','image','detail','max_edge','wire'}:
                    raise ValueError('Unsupported fields; no action or capture options')
                if request.get('wire', 'full') not in ('full', 'planner') or type(request.get('wire', 'full')) is not str:
                    raise ValueError('wire must be full or planner')
                if 'id' in request:
                    request_id = request['id']
                    if not isinstance(request_id,str) or not request_id.strip() or len(request_id)>80:
                        request_id = None
                        raise ValueError('Invalid request ID')
                snapshot_id = (request['snapshot'].get('snapshot_id')
                               if isinstance(request['snapshot'],dict) else None)
                if snapshot_id in recent_ids:
                    raise ValueError('Snapshot ID already processed; capture a new observation after the last request')
                started = time.perf_counter()
                packet = dispatch(request['snapshot'], request['queries'],
                                  image=request.get('image'),
                                  max_edge=request.get('max_edge',1600),
                                  detail=request.get('detail','brief'),
                                  ocr_fn=local_ocr, metrics=metrics)
                # Bound session memory while preventing accidental replay of
                # a recently used observation (combine same-screen targets).
                recent_order.append(snapshot_id)
                recent_ids.add(snapshot_id)
                if len(recent_order) > 1024:
                    recent_ids.discard(recent_order.popleft())
                packet.update(status='routed', request_id=request_id,
                              ocr_session_started=session is not None,
                              session_ocr_requests=session.requests if session is not None else 0,
                              observation_reused=False)
                response = packet
                if request.get('wire') == 'planner':
                    from tavi_observe_wire import planner_packet
                    response = planner_packet(packet)
                if metrics is not None:
                    metrics.record_stage('stream_request', (time.perf_counter()-started)*1000)
                    wire_bytes = len(json.dumps(response, ensure_ascii=False,
                                                allow_nan=False, separators=(',', ':')).encode('utf-8'))
                    metrics.observe(packet, wire_bytes=wire_bytes)
                    response['telemetry'] = metrics.summary()
                emit(response)
            except (ValueError, TypeError, RuntimeError, OSError,
                    OverflowError, RecursionError) as error:
                emit(dict(status='error', request_id=request_id, error=str(error),
                          authorization_granted=False, executed_actions=False))
                if session is not None and session.closed:
                    break
    finally:
        if session is not None:
            session.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(run())
