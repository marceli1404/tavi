"""Optional read-only Playwright page -> Tavi DOM control snapshot adapter.

Pass a live, trusted Playwright Page instance from an existing browser
driver. This module does not launch a browser, capture images, click,
navigate, read form values, or grant permission. The page's DOM and
accessible-name approximations are untrusted data; the host still must
revalidate the actual control immediately before an authorized action.

Requires no Playwright import: it consumes Page.evaluate, so the owning
driver can manage installation, login, session and security boundaries.
"""
from datetime import datetime, timezone
import uuid

from tavi_controls import ControlIndex

# This is an accessible-name *approximation*, not a complete ARIA tree.
# It does not inspect text-field values, password data, cookies, localStorage,
# script content, document URLs, or page-global task instructions.
_DOM_SCRIPT = r"""() => {
  const roles = new Set(['button','link','tab','checkbox','switch','radio',
                         'menuitem','textbox','combobox']);
  const selector = 'button,a[href],input:not([type="hidden"]),select,textarea,' +
      '[role="button"],[role="link"],[role="tab"],[role="checkbox"],' +
      '[role="switch"],[role="radio"],[role="menuitem"],' +
      '[role="textbox"],[role="combobox"]';
  const nodes = Array.from(document.querySelectorAll(selector));
  if (nodes.length > 10000) throw new Error('Too many DOM control candidates');
  const clean = value => (typeof value === 'string'
      ? value.replace(/\s+/g,' ').trim().slice(0,4000) : '');
  const roleFor = element => {
    const explicit = clean(element.getAttribute('role')).toLowerCase();
    if (roles.has(explicit)) return explicit;
    const tag = element.tagName.toLowerCase();
    const type = clean(element.getAttribute('type')).toLowerCase();
    if (tag === 'button') return 'button';
    if (tag === 'a' && element.hasAttribute('href')) return 'link';
    if (tag === 'select') return 'combobox';
    if (tag === 'textarea') return 'textbox';
    if (tag === 'input') {
      if (type === 'checkbox' || type === 'radio') return type;
      if (['submit','button','reset','image'].includes(type)) return 'button';
      if (type === 'hidden') return null;
      return 'textbox';
    }
    return null;
  };
  const readableText = el => clean(el.innerText || el.textContent || '');
  const nameOf = element => {
    let name = clean(element.getAttribute('aria-label'));
    if (name) return name;
    const described = clean(element.getAttribute('aria-labelledby'));
    if (described) {
      const ids = described.split(' ').slice(0,12);
      name = clean(ids.map(id => document.getElementById(id))
                   .filter(Boolean).map(readableText).join(' '));
      if (name) return name;
    }
    if (element.labels && element.labels.length) {
      name = clean(Array.from(element.labels).map(readableText).join(' '));
      if (name) return name;
    }
    // An input's current value is deliberately never read.
    name = clean(element.getAttribute('placeholder'));
    if (name) return name;
    name = clean(element.getAttribute('title'));
    if (name) return name;
    return readableText(element);
  };
  const contextOf = element => {
    const group = element.closest('[role="group"],fieldset,nav,form,section');
    if (!group) return '';
    return clean(group.getAttribute('aria-label') ||
                 (group.querySelector('legend') || {}).textContent ||
                 group.getAttribute('id') || '');
  };
  const controls = [];
  nodes.forEach((element,index) => {
    const role = roleFor(element);
    if (!role) return;
    const label = nameOf(element);
    if (!label) return;
    const rect = element.getBoundingClientRect();
    const style = window.getComputedStyle(element);
    const visible = element.getClientRects().length > 0 &&
       style.display !== 'none' && style.visibility !== 'hidden' &&
       !element.closest('[aria-hidden="true"],[hidden]');
    const enabled = !(element.disabled === true ||
                      element.closest('[aria-disabled="true"],[inert]'));
    controls.push({
      id: 'dom-' + index + '-' + clean(element.getAttribute('id')).slice(0,120),
      role, label, context: contextOf(element),
      visible: !!visible, enabled: !!enabled,
      bounds: [rect.x,rect.y,rect.width,rect.height]
    });
  });
  return { viewport:[window.innerWidth,window.innerHeight], controls };
}"""


def capture_controls(page, *, snapshot_id=None):
    """Read one current page; returns a validated, host-time-stamped snapshot."""
    if snapshot_id is None:
        snapshot_id = uuid.uuid4().hex
    if not isinstance(snapshot_id, str) or not snapshot_id.strip() or len(snapshot_id)>200:
        raise ValueError('Invalid snapshot ID')
    observed = page.evaluate(_DOM_SCRIPT)
    if (not isinstance(observed,dict)
            or set(observed) != {'viewport','controls'}):
        raise ValueError('Invalid browser control observation')
    data = {
        'format':'tavi-control-snapshot-v1',
        'snapshot_id':snapshot_id,
        'captured_at':datetime.now(timezone.utc).isoformat(),
        'source':'supported_browser_dom',
        'viewport':observed['viewport'],
        'controls':observed['controls'],
    }
    # Fail closed on invalid page records, geometry, duplicates or oversized
    # inventories before other routing code relies on the snapshot.
    ControlIndex(data)
    return data
