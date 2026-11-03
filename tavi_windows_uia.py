"""Read-only, window-scoped Windows UI Automation -> Tavi exact-control hints.

The trusted Computer host supplies an already-authorized HWND. Only the
matching controls are returned; all accessible descendants are examined
within strict node/depth limits to detect duplicates. No screen scraping,
clipboard, form values, desktop-wide search, focus, Invoke, click or typing.
Provider text is untrusted. These hints can NEVER authorize an action.

Actual Windows usage requires optional "uiautomation" (2.0.x); mocked
providers allow deterministic cross-platform safety tests.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
import sys
import time
import uuid

from tavi_controls import ControlIndex, normalized, ROLES
from tavi_observe import dispatch
from tavi_observe_wire import planner_packet

ROLES_BY_TYPE = {
    'ButtonControl':'button', 'SplitButtonControl':'button',
    'TabItemControl':'tab', 'HyperlinkControl':'link',
    'MenuItemControl':'menuitem', 'CheckBoxControl':'checkbox',
    'RadioButtonControl':'radio', 'ComboBoxControl':'combobox',
    'EditControl':'textbox',
}
MAX_NODES = 1500
MAX_DEPTH = 12


class NativeUIAUnavailable(RuntimeError):
    """The Windows UIA provider is absent, inaccessible or cannot be trusted."""


class _RealUIA:
    def __init__(self):
        if sys.platform != 'win32':
            raise NativeUIAUnavailable('Windows-only UI Automation provider')
        try:
            import uiautomation as auto
        except ImportError as exc:
            raise NativeUIAUnavailable('Install optional uiautomation==2.0.29 on Windows') from exc
        self.auto = auto

    def get_root(self, hwnd):
        try:
            return self.auto.ControlFromHandle(hwnd)
        except Exception as exc:
            raise NativeUIAUnavailable('UI Automation could not open the authorised window') from exc


def _rect(control):
    value = control.BoundingRectangle
    try:
        numbers = tuple(float(getattr(value, key)) for key in
                        ('left','top','right','bottom'))
    except (TypeError,AttributeError,ValueError) as exc:
        raise NativeUIAUnavailable('Invalid UIA rectangle') from exc
    if not all(math.isfinite(item) for item in numbers):
        raise NativeUIAUnavailable('Non-finite UIA geometry')
    if numbers[2] <= numbers[0] or numbers[3] <= numbers[1]:
        raise NativeUIAUnavailable('Empty UIA window rectangle')
    return numbers


def _validate_queries(queries):
    if not isinstance(queries,list) or not 1 <= len(queries) <= 16:
        raise ValueError('Provide 1–16 scoped control queries')
    ids=set()
    for query in queries:
        if (not isinstance(query,dict) or
                set(query)-{'id','task','target','role','context'} or
                not {'task','target'} <= set(query)):
            raise ValueError('Invalid scoped query')
        for key in ('task','target'):
            if (not isinstance(query[key],str) or
                    not query[key].strip() or len(query[key]) > 4096):
                raise ValueError('Invalid query text')
        role=query.get('role','button')
        if role not in ROLES:
            raise ValueError('Unsupported role')
        context=query.get('context')
        if context is not None and (not isinstance(context,str) or
                                    not context.strip() or len(context)>4096):
            raise ValueError('Invalid context')
        ident=query.get('id')
        if ident is not None:
            if not isinstance(ident,str) or not ident.strip() or len(ident)>200 or ident in ids:
                raise ValueError('Invalid or duplicate query ID')
            ids.add(ident)


@dataclass(frozen=True)
class NativeObservation:
    """Private host-side binding. NEVER send this object to an AI planner."""
    hwnd: int
    screen_rect: tuple[float,float,float,float]
    snapshot: dict
    queries: tuple
    result: dict


def capture_scoped_window(hwnd, queries, *, provider=None, max_nodes=MAX_NODES,
                          max_depth=MAX_DEPTH):
    """Read a specific already-authorised window, never the whole desktop.

    Its snapshot contains only exact target/role matches. All encountered
    descendants count toward traversal bounds. Enumeration error or truncated
    traversal fails closed so missing duplicate controls cannot look unique.
    Coordinates are *window-relative* UIA pixels; Computer owns any actual
    coordinate conversion and action execution.
    """
    if type(hwnd) is not int or hwnd<=0:
        raise ValueError('A positive, host-authorised window handle is required')
    _validate_queries(queries)
    if (type(max_nodes) is not int or not 1<=max_nodes<=10000 or
            type(max_depth) is not int or not 1<=max_depth<=32):
        raise ValueError('Invalid traversal bounds')
    from copy import deepcopy
    try:
        backend=provider if provider is not None else _RealUIA()
        root=backend.get_root(hwnd)
        if root is None or int(root.NativeWindowHandle)!=hwnd:
            raise NativeUIAUnavailable('Window handle mismatch')
        screen_rect=_rect(root)
        x0,y0,x1,y1=screen_rect
        width,height=x1-x0,y1-y0
        if not 0<width<=32768 or not 0<height<=32768:
            raise NativeUIAUnavailable('Unsupported window dimensions')

        wanted={(normalized(q['target']),q.get('role','button'))
                for q in queries}
        controls=[]
        # DFS path is an ephemeral identity; changed hierarchy fails recheck.
        stack=[(node,(index,),0,'')
               for index,node in reversed(list(enumerate(root.GetChildren())))]
        seen=0
        while stack:
            node,path,depth,context=stack.pop()
            seen+=1
            if seen>max_nodes or depth>=max_depth:
                raise NativeUIAUnavailable('Native accessibility tree too large')
            kind=str(node.ControlTypeName)
            role=ROLES_BY_TYPE.get(kind)
            name=node.Name
            if not isinstance(name,str):
                raise NativeUIAUnavailable('Invalid accessible name')
            if len(name)>4096:
                name=name[:4096]
            if role is not None and name.strip() and (normalized(name),role) in wanted:
                rect=node.BoundingRectangle
                coords=tuple(float(getattr(rect,field)) for field in
                             ('left','top','right','bottom'))
                if not all(math.isfinite(n) for n in coords):
                    raise NativeUIAUnavailable('Non-finite control geometry')
                a,b,c,d=coords
                if c<a or d<b:
                    raise NativeUIAUnavailable('Negative control rectangle')
                ident='uia-'+'.'.join(map(str,path))
                # Only read Name, AutomationId and UIA state. Never read
                # ValuePattern, TextPattern, a password, document or input.
                enabled=node.IsEnabled
                offscreen=node.IsOffscreen
                if type(enabled) is not bool or type(offscreen) is not bool:
                    raise NativeUIAUnavailable('Invalid accessible state')
                controls.append(dict(
                    id=ident,label=name,role=role,context=context,
                    visible=not offscreen,enabled=enabled,
                    bounds=[a-x0,b-y0,c-a,d-b]))
            next_context=context
            if kind in ('GroupControl','ToolBarControl','TabControl','MenuControl'):
                label=name.strip()
                if label:
                    next_context=label[:256]
            children=node.GetChildren()
            if children is None:
                raise NativeUIAUnavailable('UIA children unavailable')
            stack.extend((child,(*path,index),depth+1,next_context)
                         for index,child in reversed(list(enumerate(children))))
        if _rect(root)!=screen_rect or int(root.NativeWindowHandle)!=hwnd:
            raise NativeUIAUnavailable('Window moved or changed during capture')
        snapshot=dict(
            format='tavi-control-snapshot-v1',
            snapshot_id=uuid.uuid4().hex,
            captured_at=datetime.now(timezone.utc).isoformat(),
            source='supported_native',viewport=[width,height],
            controls=controls)
        ControlIndex(snapshot)
        return snapshot,screen_rect
    except NativeUIAUnavailable:
        raise
    except (AttributeError,ValueError,TypeError,OverflowError,RuntimeError) as exc:
        raise NativeUIAUnavailable('Unable to read complete native accessibility window') from exc


def observe_window(hwnd, queries, *, provider=None, max_nodes=MAX_NODES):
    """Fresh, scoped, deterministic suggestion; no action is possible."""
    state,bounds=capture_scoped_window(
        hwnd,queries,provider=provider,max_nodes=max_nodes)
    result=dispatch(state,queries)
    return NativeObservation(
        hwnd=hwnd,screen_rect=bounds,snapshot=state,
        queries=tuple(tuple(sorted(q.items())) for q in queries),
        result=result)


def planner_view(observation):
    if not isinstance(observation, NativeObservation):
        raise ValueError('Expected trusted host observation')
    return planner_packet(observation.result)


def revalidate_window(observation, *, provider=None, max_nodes=MAX_NODES):
    """A *fresh* recheck of exact identity; never performs an action.

    Returns a boolean and non-authoritative reason only. The Computer host
    must independently authorize and carry out the click and verify success.
    Recheck must also reject the original snapshot once it becomes stale.
    """
    if not isinstance(observation,NativeObservation):
        raise ValueError('Expected trusted host observation')
    queries=[dict(items) for items in observation.queries]
    original=dispatch(observation.snapshot,queries)
    if (original['snapshot_sha256']!=observation.result['snapshot_sha256'] or
        original['authorization_granted'] is not False or
        original['executed_actions'] is not False or
        any(row['route']!='host_control' for row in original['routes'])):
        return False,'original_missing_ambiguous_or_stale'
    state,bounds=capture_scoped_window(
        observation.hwnd,queries,provider=provider,max_nodes=max_nodes)
    if bounds!=observation.screen_rect:
        return False,'window_geometry_changed'
    newest=dispatch(state,queries)
    for old,new in zip(original['routes'],newest['routes']):
        if new['route']!='host_control':
            return False,'current_control_not_exact'
        if old['control']['candidate']!=new['control']['candidate']:
            return False,'control_identity_changed'
    return True,'fresh_exact_match_still_requires_computer_authorization'
