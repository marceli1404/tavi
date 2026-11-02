"""Stateless JSON-lines exact-control requests. No capture, network or actions."""
import json
import sys
from tavi_controls import resolve_many
MAX_REQUEST_BYTES=2_000_000

def _object(pairs):
 result={}
 for key,value in pairs:
  if key in result:raise ValueError('Duplicate JSON field')
  result[key]=value
 return result

def run(input_stream=None,output_stream=None):
 input_stream=sys.stdin if input_stream is None else input_stream
 output_stream=sys.stdout if output_stream is None else output_stream
 for stream in (input_stream,output_stream):
  if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8')
 def emit(value):output_stream.write(json.dumps(value,ensure_ascii=False,allow_nan=False)+'\n');output_stream.flush()
 emit(dict(status='ready',format='tavi-control-stream-v1',requires_live_host_check=True,authorization_granted=False,executed_actions=False))
 while True:
  line=input_stream.readline(MAX_REQUEST_BYTES+1)
  if not line:break
  if len(line)>MAX_REQUEST_BYTES or len(line.encode('utf-8'))>MAX_REQUEST_BYTES:
   emit(dict(status='error',error='Control request exceeds2MB',authorization_granted=False,executed_actions=False));return 1
  request_id=None
  try:
   request=json.loads(line,object_pairs_hook=_object)
   if not isinstance(request,dict) or set(request)-{'id','snapshot','queries','compact'} or not {'snapshot','queries'}<=set(request):raise ValueError('Expected snapshot and queries; no offline, capture or action options')
   if 'compact' in request and type(request['compact']) is not bool:raise ValueError('compact must be boolean')
   if 'id' in request:
    ident=request['id']
    if not isinstance(ident,str) or not ident.strip() or len(ident)>80:raise ValueError('Invalid request ID')
    request_id=ident
   result=resolve_many(request['snapshot'],request['queries'])
   if request.get('compact',False):
    from tavi_control_compact import compact_batch
    result=compact_batch(result)
   result.update(request_id=request_id,observation_reused=False)
   emit(result)
  except (ValueError,TypeError,OverflowError,RecursionError) as error:
   emit(dict(request_id=request_id,status='error',error=str(error),authorization_granted=False,executed_actions=False))
 return 0
