"""JSON-lines local proposals for a computer-use session; never hosted calls or input actions."""
import json
import sys
import time
from tavi_compact import propose
from tavi_ocr import OcrSession

def run(input_stream=None,output_stream=None,session_factory=OcrSession,auto_click=False):
    if input_stream is None:
        input_stream=sys.stdin
        if hasattr(input_stream,'reconfigure'): input_stream.reconfigure(encoding='utf-8')
    if output_stream is None:
        output_stream=sys.stdout
        if hasattr(output_stream,'reconfigure'): output_stream.reconfigure(encoding='utf-8')
    def emit(value):
        output_stream.write(json.dumps(value,ensure_ascii=False)+'\n'); output_stream.flush()
    started=time.perf_counter()
    with session_factory() as session:
        emit({'status':'ready','mode':'local_proposals','startup_ms':round((time.perf_counter()-started)*1000,2)})
        while True:
            line=input_stream.readline(16385)
            if not line: break
            if len(line)>16384:
                emit({'status':'error','error':'Request exceeds16384 characters'}); break
            request_id=None
            try:
                request=json.loads(line)
                if not isinstance(request,dict): raise ValueError('Request must be an object')
                request_id=request.get('id')
                if request_id is not None and (not isinstance(request_id,str) or len(request_id)>80):
                    raise ValueError('Request id must be a string of at most80 characters')
                if set(request)-{'id','image','task','target','max_edge'}: raise ValueError('Unsupported request fields; stream is local-only')
                if not all(isinstance(request.get(k),str) for k in ('image','task','target')):
                    raise ValueError('image, task and target must be strings')
                if 'max_edge' in request and type(request['max_edge']) is not int:
                    raise ValueError('max_edge must be an integer')
                options=dict(max_edge=request.get('max_edge',1600),ocr_fn=session)
                if auto_click: options['auto_click']=True
                result=propose(request['image'],request['task'],request['target'],**options)
                result.update(request_id=request_id,session_ocr_requests=session.requests,proposal_reused=False)
                emit(result)
            except (OSError,ValueError,RuntimeError) as error:
                emit({'request_id':request_id,'status':'error','error':str(error)})
                if session.closed: break
    return 0
