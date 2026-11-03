"""Warm offline predictions from one verified model load.

The stream never runs hosted inference, captures a screen, chooses permissions,
or executes any action. Every prediction is independently computed; task
contexts and prior answers are not cached or retained between requests.
"""
import json
import sys

MAX_REQUEST_BYTES = 65_536
MAX_REQUESTS = None  # One bounded request per line; host controls session life.


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON field')
        result[key] = value
    return result


def run(model, input_stream=None, output_stream=None):
    """Serve independent prompt predictions; use the same infer path as CLI."""
    input_stream = sys.stdin if input_stream is None else input_stream
    output_stream = sys.stdout if output_stream is None else output_stream
    for stream in (input_stream, output_stream):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')

    def emit(value):
        output_stream.write(json.dumps(value, ensure_ascii=False, allow_nan=False,
                                      separators=(',', ':')) + '\n')
        output_stream.flush()

    emit(dict(status='ready', format='tavi-predict-stream-v1',
              model_artifact=model.metadata['weights_sha256'],
              no_hosted_inference=True, authorization_granted=False,
              executed_actions=False))

    while True:
        line = input_stream.readline(MAX_REQUEST_BYTES + 1)
        if not line:
            break
        if len(line) > MAX_REQUEST_BYTES or len(line.encode('utf-8')) > MAX_REQUEST_BYTES:
            emit(dict(status='error', error='Prediction request exceeds 64 KiB',
                      authorization_granted=False, executed_actions=False))
            return 1
        request_id = None
        try:
            request = json.loads(line, object_pairs_hook=_unique_object,
                                 parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Non-finite JSON value')))
            if not isinstance(request, dict) or set(request) - {'id', 'prompt', 'top_k'}:
                raise ValueError('Expected prompt, optional ID and top_k only')
            if 'id' in request:
                request_id = request['id']
                if not isinstance(request_id, str) or not request_id.strip() or len(request_id) > 80:
                    request_id = None
                    raise ValueError('Invalid request ID')
            prompt = request.get('prompt')
            if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 16000:
                raise ValueError('Prompt must contain 1–16000 characters')
            top_k = request.get('top_k', 8)
            if type(top_k) is not int or not 0 <= top_k <= 8:
                raise ValueError('top_k must be an integer in 0–8')
            prediction = model.infer(prompt)
            prediction['skills'] = prediction['skills'][:top_k]
            emit(dict(status='predicted', request_id=request_id,
                      format='tavi-predict-stream-v1',
                      model_artifact=model.metadata['weights_sha256'],
                      prediction=prediction,
                      no_hosted_inference=True, authorization_granted=False,
                      executed_actions=False))
        except (ValueError, TypeError, OverflowError, RecursionError) as error:
            emit(dict(request_id=request_id, status='error', error=str(error),
                      authorization_granted=False, executed_actions=False))
    return 0
