"""Supported Codex JSONL protocol; owning a stdio server is not controlling the desktop."""
import json
from pathlib import Path
import queue
import subprocess
import threading
import time
from tavi import codex_command


class RpcError(RuntimeError):
    pass


class AppServer:
    def __init__(self, transport='proxy', socket_path=None, timeout=10):
        if transport not in ('proxy','stdio'):
            raise ValueError('Transport must be proxy or stdio')
        self.transport, self.timeout = transport, timeout
        command = codex_command()+['app-server']
        if transport == 'proxy':
            command += ['proxy']
            if socket_path:
                command += ['--sock',str(Path(socket_path).resolve())]
        else:
            command += ['--stdio']
        self.process = subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                        text=True,encoding='utf-8',bufsize=1)
        self.messages, self.notifications, self.errors = queue.Queue(), [], []
        self.counter = 0
        threading.Thread(target=self._read,daemon=True).start()
        threading.Thread(target=self._stderr,daemon=True).start()
        try:
            self.server_info = self.call('initialize',dict(clientInfo=dict(name='tavi_router',title='Tavi Router',version='0.5'),
                                                         capabilities=dict(experimentalApi=True)))
            self.notify('initialized',{})
        except Exception:
            self.close()
            raise

    def _read(self):
        try:
            for line in self.process.stdout:
                try:
                    self.messages.put(json.loads(line))
                except ValueError:
                    continue
        finally:
            self.messages.put(None)

    def _stderr(self):
        for line in self.process.stderr:
            self.errors.append(line.rstrip())
            self.errors = self.errors[-12:]

    def notify(self,method,params):
        self.process.stdin.write(json.dumps(dict(method=method,params=params))+'\n')
        self.process.stdin.flush()

    def call(self,method,params):
        self.counter += 1
        ident = self.counter
        self.process.stdin.write(json.dumps(dict(id=ident,method=method,params=params))+'\n')
        self.process.stdin.flush()
        deadline = time.monotonic()+self.timeout
        while time.monotonic()<deadline:
            try:
                message = self.messages.get(timeout=max(.01,deadline-time.monotonic()))
            except queue.Empty:
                break
            if message is None:
                raise RpcError('App-server transport closed; no desktop control connection established')
            if message.get('id') == ident:
                if 'error' in message:
                    raise RpcError(str(message['error'].get('message','RPC failed')))
                return message.get('result',{})
            if 'method' in message:
                self.notifications.append(message)
        raise RpcError('App-server request timed out: '+method)

    def wait_notification(self,method,thread_id,timeout=5):
        deadline=time.monotonic()+timeout
        while True:
            found=[n for n in self.notifications if n.get('method')==method and n.get('params',{}).get('threadId')==thread_id]
            if found:
                return found[-1]['params']
            remaining=deadline-time.monotonic()
            if remaining<=0:
                raise RpcError('Expected settings notification not observed')
            try:
                message=self.messages.get(timeout=remaining)
            except queue.Empty:
                raise RpcError('Expected settings notification not observed')
            if message is None:
                raise RpcError('App-server closed before settings verification')
            if 'method' in message:
                self.notifications.append(message)

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)

    def __enter__(self):
        return self

    def __exit__(self,*args):
        self.close()


def desktop_status(socket_path=None):
    try:
        with AppServer('proxy',socket_path,timeout=5) as client:
            result=client.call('thread/loaded/list',{})
            return dict(status='connected',transport='desktop-control-proxy',loaded_threads=result,
                        capability='Next-turn settings may be updated after target/state/model validation')
    except (OSError,RuntimeError,subprocess.SubprocessError) as error:
        return dict(status='unavailable',transport='desktop-control-proxy',error=str(error),
                    changed_desktop=False,limitation='No supported desktop control socket is reachable. Do not replace this with direct edits to thread databases or private desktop IPC.')


def protocol_selftest(workspace):
    """No user message or generation; use only a disposable in-memory thread we own."""
    with AppServer('stdio',timeout=30) as client:
        models=client.call('model/list',dict(limit=20,includeHidden=False))['data']
        visible={m['id']:m for m in models}
        preferred=[m for m in ('gpt-6-luna','gpt-6.1-sol') if m in visible]
        if len(preferred)<2:
            raise RpcError('Two expected catalog models are needed for the switch test')
        start=client.call('thread/start',dict(model=preferred[0],ephemeral=True,sandbox='read-only',cwd=str(Path(workspace).resolve())))
        thread_id=start['thread']['id']
        selected=preferred[1]
        supported=[e['reasoningEffort'] for e in visible[selected]['supportedReasoningEfforts']]
        effort='medium' if 'medium' in supported else visible[selected]['defaultReasoningEffort']
        update=switch_loaded_thread(client,thread_id,selected,effort)
        settings=update.get('next_turn',{})
        verified=update['status']=='verified'
        return dict(status='verified' if verified else 'mismatch',transport='owned-stdio-server',
                    ephemeral_thread=thread_id,initial_model=preferred[0],requested_model=selected,
                    returned_model=settings.get('model'),requested_effort=effort,returned_effort=settings.get('effort'),
                    started_generation=False,desktop_thread_changed=False,
                    meaning='Protocol supports subsequent-turn settings in an owned thread; this does not establish access to desktop-owned threads')


def switch_loaded_thread(client,thread_id,model,effort):
    """Explicit next-turn update on a loaded, idle thread. Never resumes or generates."""
    loaded=client.call('thread/loaded/list',{})['data']
    if thread_id not in loaded:
        raise RpcError('Target is not loaded on this server; no automatic thread resume or disk edits')
    catalog=client.call('model/list',dict(limit=100,includeHidden=False))['data']
    entry=next((m for m in catalog if m['id']==model),None)
    if not entry:
        raise RpcError('Requested model is not visible on the connected server')
    if effort not in [e['reasoningEffort'] for e in entry['supportedReasoningEfforts']]:
        raise RpcError('Requested reasoning effort is unsupported by this model')
    thread=client.call('thread/read',dict(threadId=thread_id,includeTurns=False))['thread']
    status=thread.get('status',{})
    kind=status.get('type') if isinstance(status,dict) else status
    if kind!='idle':
        raise RpcError('Thread is not idle; model switching withheld without interrupting it')
    previous=dict(model=thread.get('model'),effort=thread.get('reasoningEffort'))
    client.notifications=[n for n in client.notifications if not(n.get('method')=='thread/settings/updated' and n.get('params',{}).get('threadId')==thread_id)]
    client.call('thread/settings/update',dict(threadId=thread_id,model=model,effort=effort))
    try:
        changed=client.wait_notification('thread/settings/updated',thread_id)['threadSettings']
    except RpcError as error:
        return dict(status='verification_unavailable',thread_id=thread_id,previous=previous,
                    requested=dict(model=model,effort=effort),update_sent=True,error=str(error),started_generation=False)
    verified=changed.get('model')==model and changed.get('effort')==effort
    return dict(status='verified' if verified else 'mismatch',thread_id=thread_id,previous=previous,
                next_turn=dict(model=changed.get('model'),effort=changed.get('effort')),
                update_sent=True,started_generation=False,current_turn_model_changed=False)


def desktop_switch(thread_id,model,effort,socket_path=None):
    with AppServer('proxy',socket_path,timeout=10) as client:
        return switch_loaded_thread(client,thread_id,model,effort)
