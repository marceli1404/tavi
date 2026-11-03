"""Warm, read-only, single-HWND Windows UIA suggestion/recheck worker.

Launch from the trusted Computer host with --window-handle <already permitted
HWND>. The worker never changes that scope, clicks, invokes, focuses, navigates,
types, opens screenshots or calls a model. JSON-lines input/output only.
"""
from __future__ import annotations

import argparse
from collections import OrderedDict
import json
import sys
import time
import uuid

from tavi_windows_uia import (
    _RealUIA, _validate_queries, observe_window, planner_view,
    revalidate_window, NativeUIAUnavailable,
)

MAX_LINE_BYTES=128*1024
MAX_OUTSTANDING=64
MAX_RECHECK_AGE_SECONDS=5.0


def _json_object(pairs):
    result={}
    for key,value in pairs:
        if key in result:
            raise ValueError('Duplicate request field')
        result[key]=value
    return result


def run(*,allowed_hwnd,input_stream=None,output_stream=None,provider=None,clock=None):
    if type(allowed_hwnd) is not int or allowed_hwnd<=0:
        raise ValueError('An authorized positive HWND is required')
    incoming=input_stream if input_stream is not None else sys.stdin
    outgoing=output_stream if output_stream is not None else sys.stdout
    now=clock if clock is not None else time.monotonic
    # Instantiate the optional COM adapter *once* and reuse it across queries.
    backend=provider if provider is not None else _RealUIA()
    pending=OrderedDict()

    def emit(event):
        outgoing.write(json.dumps(event,ensure_ascii=False,
                                  allow_nan=False,separators=(',',':'))+'\n')
        outgoing.flush()

    def sweep():
        cutoff=now()-MAX_RECHECK_AGE_SECONDS
        for key,(started,_) in list(pending.items()):
            if started<cutoff:
                del pending[key]

    emit(dict(status='ready',format='tavi-native-windows-uia-stream-v1',
              scope='one-authorized-window',planner_only=True,
              requires_live_host_check=True,
              authorization_granted=False,executed_actions=False))
    while True:
        line=incoming.readline(MAX_LINE_BYTES+1)
        if not line:
            break
        if len(line)>MAX_LINE_BYTES or len(line.encode('utf-8'))>MAX_LINE_BYTES:
            emit(dict(status='error',code='request_too_large',
                      authorization_granted=False,executed_actions=False))
            return 1
        request_id=None
        try:
            request=json.loads(line,object_pairs_hook=_json_object,
                parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Non-finite JSON')))
            if not isinstance(request,dict):
                raise ValueError('Object expected')
            request_id=request.get('id')
            if (request_id is not None and
                (not isinstance(request_id,str) or not request_id.strip()
                 or len(request_id)>80)):
                raise ValueError('Invalid request id')
            op=request.get('op')
            sweep()
            if op=='observe':
                if set(request)-{'id','op','queries'}:
                    raise ValueError('Unexpected observation fields')
                queries=request.get('queries')
                _validate_queries(queries)
                result=observe_window(allowed_hwnd,queries,provider=backend)
                token=uuid.uuid4().hex
                pending[token]=(now(),result)
                if len(pending)>MAX_OUTSTANDING:
                    pending.popitem(last=False)
                emit(dict(
                    status='observed',request_id=request_id,
                    observation_id=token,result=planner_view(result),
                    authorization_granted=False,executed_actions=False))
            elif op=='recheck':
                if set(request)-{'id','op','observation_id'}:
                    raise ValueError('Unexpected recheck fields')
                key=request.get('observation_id')
                if not isinstance(key,str) or len(key)!=32:
                    raise ValueError('Invalid observation ID')
                entry=pending.pop(key,None)
                if entry is None:
                    emit(dict(status='recheck',request_id=request_id,
                              matched=False,reason='not_found_expired_or_reused',
                              authorization_granted=False,executed_actions=False))
                    continue
                _,original=entry
                passed,reason=revalidate_window(original,provider=backend)
                emit(dict(status='recheck',request_id=request_id,
                          matched=passed,reason=reason,
                          requires_computer_authorization=True,
                          authorization_granted=False,executed_actions=False))
            else:
                raise ValueError('Unsupported request operation')
        except (ValueError,TypeError,OverflowError,RuntimeError,
                NativeUIAUnavailable) as exc:
            # Never echo raw UIA exceptions, names or COM error messages.
            emit(dict(status='error',request_id=request_id,
                      code='invalid_request' if isinstance(exc,(ValueError,TypeError))
                           else 'accessibility_unavailable',
                      authorization_granted=False,executed_actions=False))
    return 0


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--window-handle',type=int,required=True,
                        help='HWND explicitly authorized by the trusted host')
    args=parser.parse_args(argv)
    return run(allowed_hwnd=args.window_handle)


if __name__=='__main__':
    raise SystemExit(main())
