"""Bounded, explicitly owned CPU OCR process. No socket, service installation or result cache."""
import json
import os
from pathlib import Path
import queue
import subprocess
import threading


class OcrSession:
    def __init__(self,timeout=25):
        if os.name!='nt': raise RuntimeError('Reusable local OCR requires Windows')
        if not 0<timeout<=60: raise ValueError('OCR timeout must be greater than0 and at most60 seconds')
        self.timeout=timeout; self.requests=0; self.closed=False
        self._lock=threading.Lock(); self._lines=queue.Queue()
        script=Path(__file__).with_name('screen_ocr_worker.ps1').read_text(encoding='utf-8')
        self.process=subprocess.Popen(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
            text=True,encoding='utf-8',errors='strict',bufsize=1,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        def reader():
            try:
                for line in self.process.stdout: self._lines.put(line)
            finally: self._lines.put(None)
        self._reader=threading.Thread(target=reader,daemon=True); self._reader.start()
        try:
            ready=self._receive()
            if ready!={'status':'ready','protocol':1}: raise RuntimeError('Windows OCR session initialization failed')
        except Exception:
            self.close(); raise

    def _receive(self):
        try: line=self._lines.get(timeout=self.timeout)
        except queue.Empty as error:
            raise RuntimeError('Local OCR session timed out') from error
        if line is None: raise RuntimeError('Local OCR session exited')
        try: result=json.loads(line)
        except ValueError as error: raise RuntimeError('Invalid local OCR protocol response') from error
        if not isinstance(result,dict): raise RuntimeError('Invalid local OCR response')
        return result

    def __call__(self,image):
        with self._lock:
            if self.closed: raise RuntimeError('Local OCR session is closed')
            image=Path(image).resolve(strict=True)
            if image.stat().st_size>32*1024*1024: raise ValueError('Screenshot exceeds32MB')
            self.requests+=1
            request={'operation':'recognize','id':self.requests,'path':str(image)}
            try:
                self.process.stdin.write(json.dumps(request)+'\n'); self.process.stdin.flush()
                result=self._receive()
                if result.get('id')!=self.requests or result.get('status') not in ('available','unavailable'):
                    raise RuntimeError('Mismatched local OCR response')
                result.pop('id')
                return result
            except (OSError,RuntimeError,ValueError):
                self.close(); raise

    def close(self):
        if self.closed: return
        self.closed=True
        try:
            if self.process.poll() is None:
                try:
                    self.process.stdin.write('{"operation":"close"}\n'); self.process.stdin.flush()
                    self.process.wait(timeout=2)
                except (OSError,subprocess.TimeoutExpired):
                    self.process.kill(); self.process.wait(timeout=2)
        finally:
            try: self.process.stdin.close()
            except OSError: pass
            self._reader.join(timeout=2)
            self.process.stdout.close()

    def __enter__(self): return self
    def __exit__(self,*args): self.close()
