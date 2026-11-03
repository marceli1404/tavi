"""Local-only, deterministic Playwright *fixture* computer-use benchmark.

Runs in a browser created here and populated only with embedded HTML.
No user website, credentials, network destination, arbitrary task, model or
external browser session can be supplied. This harness deliberately performs
one verified click in its own test page; production Tavi never clicks.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from tavi_browser_snapshot import capture_controls
from tavi_metrics import UsageMetrics
from tavi_observe import dispatch

_SIMPLE = """<!doctype html><html data-tavi-fixture="v1"><body>
<button id="go" onclick="document.getElementById('result').textContent='clicked'">Go</button>
<output id="result">pending</output></body></html>"""
_DISABLED = """<!doctype html><html data-tavi-fixture="v1"><body>
<button id="go" disabled onclick="document.getElementById('result').textContent='clicked'">Go</button>
<output id="result">pending</output></body></html>"""
_AMBIGUOUS = """<!doctype html><html data-tavi-fixture="v1"><body>
<button id="go1">Go</button><button id="go2">Go</button>
<output id="result">pending</output></body></html>"""
_MISSING = """<!doctype html><html data-tavi-fixture="v1"><body>
<span>Go</span><output id="result">pending</output></body></html>"""

_QUERY = {'id':'fixture-go','task':'Inspect the fixture button','target':'Go','role':'button'}


def _observe(page, metrics):
    snap = capture_controls(page, metrics=metrics)
    with metrics.stage('stream_request'):
        result = dispatch(snap, [_QUERY], metrics=metrics)
    metrics.observe(result)
    return result['routes'][0]


def _fixture_page(page):
    # This check is defensive in depth; run_fixture_suite creates the
    # browser/page itself and never accepts an external page or URL.
    return (page.url == 'about:blank' and
            page.locator('html[data-tavi-fixture="v1"]').count() == 1)


def _verified_fixture_click(page, original, metrics):
    """Fail closed on changed DOM, duplicate, hidden or disabled controls."""
    if not _fixture_page(page) or original.get('route') != 'host_control':
        return False
    before = original['control']['candidate']
    with metrics.stage('host_recheck'):
        current = _observe(page, metrics)
        if current['route'] != 'host_control':
            return False
        after = current['control']['candidate']
        if (before['id'] != after['id'] or
                before['label'] != after['label'] or
                before['role'] != after['role'] or
                before['context'] != after['context'] or
                before['bounds'] != after['bounds']):
            return False
        locator = page.get_by_role('button', name='Go', exact=True)
        if locator.count() != 1 or not locator.is_visible() or not locator.is_enabled():
            return False
        geometry = locator.bounding_box()
        if geometry is None:
            return False
        bounds = after['bounds']
        if any(abs(geometry[key]-bounds[i])>1 for i,key in
               enumerate(('x','y','width','height'))):
            return False

    with metrics.stage('action'):
        locator.click(timeout=2000)
    with metrics.stage('result_verify'):
        return page.locator('#result').inner_text(timeout=2000) == 'clicked'


def run_fixture_suite(*, repeats=3):
    if type(repeats) is not int or not 1<=repeats<=25:
        raise ValueError('repeats must be an integer from 1 to 25')
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError('Optional Playwright required: pip install -r requirements-browser-eval.txt') from exc

    metrics = UsageMetrics()
    results = dict(
        expected_clicks=0, verified_clicks=0, unexpected_clicks=0,
        expected_safety_blocks=0, safety_blocks=0, failures=0,
    )
    started = time.perf_counter()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width':800,'height':600},
                                    service_workers='block')
            # Local test pages make no external requests. Any attempted
            # remote request is blocked rather than fetching the network.
            page.route('**/*', lambda route: route.abort())
            for _ in range(repeats):
                page.set_content(_SIMPLE)
                initial = _observe(page, metrics)
                results['expected_clicks'] += 1
                clicked = _verified_fixture_click(page, initial, metrics)
                results['verified_clicks'] += int(clicked)
                results['failures'] += int(not clicked)

                for html, expected in (
                    (_DISABLED,'host_review'), (_AMBIGUOUS,'host_review'),
                    (_MISSING,'needs_screenshot')
                ):
                    page.set_content(html)
                    route = _observe(page, metrics)
                    results['expected_safety_blocks'] += 1
                    allowed = _verified_fixture_click(page, route, metrics)
                    blocked = route['route'] == expected and not allowed
                    results['safety_blocks'] += int(blocked)
                    results['failures'] += int(not blocked)
                    results['unexpected_clicks'] += int(allowed)

                page.set_content(_SIMPLE)
                initial = _observe(page, metrics)
                # An action must NOT use a locator from an obsolete
                # observation, even if the previous proposal was exact.
                page.eval_on_selector('#go',"(element) => element.textContent = 'Changed'")
                results['expected_safety_blocks'] += 1
                allowed = _verified_fixture_click(page, initial, metrics)
                blocked = not allowed
                results['safety_blocks'] += int(blocked)
                results['failures'] += int(not blocked)
                results['unexpected_clicks'] += int(allowed)
        finally:
            browser.close()
    summary = {
        'format':'tavi-playwright-local-fixture-eval-v1',
        'scope':'Fresh local Chromium about:blank HTML only; no websites, user data, hosted model, OCR, OSWorld or WebArena.',
        'repeats':repeats,
        'scenarios':['exact_control','disabled_control','ambiguous_control',
                     'missing_control','changed_control_before_click'],
        'outcomes':results,
        'elapsed_ms':round((time.perf_counter()-started)*1000,3),
        'metrics':metrics.summary(),
        'real_browser_exercised':True,
        'real_website_tasks_measured':False,
        'end_to_end_agent_performance_measured':False,
        'host_model_tokens_measured':False,
        'production_click_backend_added':False,
    }
    if results['failures'] or results['unexpected_clicks']:
        raise AssertionError('Local Playwright fixture verification failed: '+str(results))
    return summary


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repeats',type=int,default=3)
    parser.add_argument('--output',type=Path,help='Optional NEW local JSON report (never overwritten)')
    args=parser.parse_args(argv)
    report=run_fixture_suite(repeats=args.repeats)
    if args.output:
        with args.output.open('x',encoding='utf-8') as file:
            json.dump(report,file,indent=2,ensure_ascii=False)
            file.write('\n')
    print(json.dumps(report,indent=2,ensure_ascii=False))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
