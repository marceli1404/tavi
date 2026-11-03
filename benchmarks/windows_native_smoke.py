"""Optional true Windows UIA smoke measurement against a local Tk fixture.

This measures accessibility collection and Tavi routing ONLY. It never
clicks, types, sees a user app, invokes Computer or infers full-task speedup.
On non-interactive CI desktops reports "not_measured" (NOT a passing native
capture benchmark). Only the generated test window may be observed.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time

from tavi_computer_native import NativeComputerAdapter, WindowsUiaWorker


def run(*, repeats=5):
    if type(repeats) is not int or not 1<=repeats<=20:
        raise ValueError('repeats must be a small positive integer')
    report=dict(
        format='tavi-windows-ui-automation-smoke-v1',
        scope='Generated local Tk button only; not Computer, real websites or full task execution.',
        repeats=repeats,real_windows_uia_exercised=False,
        screenshots=0, executed_actions=0,hosted_model_calls=0,
        actual_provider_tokens_measured=False,
        status='not_measured',reason=None)
    if sys.platform!='win32':
        report['reason']='not_windows'
        return report
    root=None
    worker=None
    try:
        import ctypes
        import tkinter as tk
        root=tk.Tk()
        root.title('Tavi locally generated UI Automation fixture')
        root.geometry('430x280+120+120')
        root.lift()
        root.attributes('-topmost',True)
        button=tk.Button(root,text='Favorites',font=('Arial',18))
        button.pack(pady=65)
        root.update()
        root.focus_force()
        root.update()
        user32=ctypes.windll.user32
        hwnd=int(user32.GetAncestor(int(root.winfo_id()),2))
        user32.SetForegroundWindow(hwnd)
        root.update()
        if hwnd<=0 or int(user32.GetForegroundWindow())!=hwnd:
            report['reason']='fixture_not_foreground'
            return report
        worker=WindowsUiaWorker(timeout_seconds=8)
        adapter=NativeComputerAdapter(worker)
        direct=[]
        routed=[]
        exact=0
        for _ in range(repeats):
            root.update()
            if int(user32.GetForegroundWindow())!=hwnd:
                report['reason']='fixture_lost_foreground'
                return report
            a=time.perf_counter()
            raw=worker.capture()
            direct.append((time.perf_counter()-a)*1000)
            if raw['window_binding']['hwnd']!=hwnd:
                report['reason']='foreground_provenance_mismatch'
                return report
            b=time.perf_counter()
            result=adapter.handle(dict(
                op='suggest',target='Favorites',role='button'))
            routed.append((time.perf_counter()-b)*1000)
            if result['window_binding']['hwnd']!=hwnd:
                report['reason']='foreground_provenance_mismatch'
                return report
            exact+=result['rows'][0][1]=='host_control'
            if result['authorization_granted'] or result['executed_actions']:
                raise AssertionError('Read-only host authority contract violated')
        report.update(
            status='measured',reason=None,
            real_windows_uia_exercised=True,
            exact_label_matches=exact,
            direct_uia_capture_median_ms=round(statistics.median(direct),3),
            direct_uia_capture_times_ms=[round(value,3) for value in direct],
            native_uia_plus_tavi_median_ms=round(statistics.median(routed),3),
            native_uia_plus_tavi_times_ms=[round(value,3) for value in routed])
        return report
    except AssertionError:
        raise
    except Exception:
        # Never expose potentially sensitive native/UI exception detail.
        report['reason']='unsupported_interactive_environment_or_uia'
        report['status']='not_measured'
        return report
    finally:
        if worker is not None:
            worker.close()
        if root is not None:
            try:
                root.destroy()
            except Exception:
                pass


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repeats',type=int,default=5)
    args=parser.parse_args(argv)
    report=run(repeats=args.repeats)
    print(json.dumps(report,indent=2))
    # A legitimately inaccessible Windows GUI should not be presented as an
    # observed successful native benchmark. Its JSON says "not_measured".
    return 0


if __name__=='__main__':
    raise SystemExit(main())
