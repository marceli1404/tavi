"""Matched 3-step Chromium fixture workflows: screenshot+real Tesseract OCR vs Tavi.

BOTH approaches run on the same fixed, generated, non-sensitive browser pages.
They receive identical pre-scripted goals and use page.mouse.click, a fresh
observation immediately before each action, and the same result verifier.
The screenshot route cannot use DOM/accessibility for target selection; Tavi
uses capture_controls + dispatch and never reads screenshots in these tasks.
Neither route uses a hosted model or claims autonomous-agent parity.
External requests are blocked. Never accepts an external URL or user browser.
"""
from __future__ import annotations

from collections import Counter
from io import BytesIO
from pathlib import Path
import argparse
import json
import math
import statistics
import time

TASKS = {
    'onboarding': ('Begin', 'Continue', 'Finish'),
    'settings': ('Settings', 'Alerts', 'Save'),
    'auditing': ('Audit', 'Check', 'Report'),
    'catalog': ('Find', 'Filter', 'Open'),
}
MODES = ('screenshot_ocr', 'tavi_dom')


def fixture(steps):
    if tuple(steps) not in TASKS.values():
        raise ValueError('Only fixed local fixture tasks are allowed')
    return """<!doctype html><html data-tavi-matched-fixture="v1">
<head><meta charset="utf-8"><style>
body{font-family:Arial,sans-serif;background:#fff;color:#171717;margin:0}
main{margin:75px 0 0 96px;width:650px}
h1{font-size:36px;font-weight:700;margin:0 0 15px}
p{font-size:20px;margin:0 0 25px;color:#444}
button{cursor:pointer;border:2px solid #151515;border-radius:8px;
background:#fff;color:#151515;font-family:Arial,sans-serif;
font-size:30px;font-weight:700;line-height:1.25;
padding:22px 42px;min-width:225px;text-align:center}
output{display:block;margin:26px 0;font-size:22px}
</style></head><body><main><h1>Workflow testing</h1>
<p>Complete the sequence using the action below.</p>
<button id="action" type="button"></button>
<output id="phase">Ready</output>
</main><script>
const steps = """ + json.dumps(list(steps)) + """;
let position = 0;
const control = document.getElementById('action');
const phase = document.getElementById('phase');
control.textContent = steps[position];
control.addEventListener('click', () => {
 position += 1;
 if (position === steps.length) {
   phase.textContent = 'Verified complete';
   control.remove();
 } else {
   control.textContent = steps[position];
   phase.textContent = 'Next stage ready';
 }
});
</script></body></html>"""


def is_fixture(page):
    return (page.url == 'about:blank' and
            page.locator('html[data-tavi-matched-fixture="v1"]').count() == 1)


def screen_ocr_target(page, label, counters):
    """Image-only dark-rectangle proposal + real cropped OCR; no DOM locator."""
    import numpy as np
    import pytesseract
    from PIL import Image

    screenshot = page.screenshot(type='png', full_page=False)
    counters['screenshots'] += 1
    counters['screenshot_bytes'] += len(screenshot)
    image = Image.open(BytesIO(screenshot)).convert('RGB')
    dark = np.asarray(image.convert('L')) < 90
    edges = []
    for y, row in enumerate(dark):
        runs = np.flatnonzero(np.diff(np.r_[False,row,False]))
        if not len(runs):
            continue
        widths = runs[1::2]-runs[::2]
        best = int(np.argmax(widths))
        if widths[best] > 140:
            edges.append((y,int(runs[::2][best]),int(runs[1::2][best])))
    groups = []
    for y,left,right in edges:
        if groups and y <= groups[-1][-1][0]+2:
            groups[-1].append((y,left,right))
        else:
            groups.append([(y,left,right)])
    matches = []
    for i, first_group in enumerate(groups):
        top = first_group[0]
        for last_group in groups[i+1:]:
            bottom = last_group[-1]
            if not 40 <= bottom[0]-top[0] <= 170:
                continue
            if abs(top[1]-bottom[1])>10 or abs(top[2]-bottom[2])>10:
                continue
            left = max(top[1],bottom[1])+6
            right = min(top[2],bottom[2])-6
            upper,lower = top[0]+6,bottom[0]-6
            if right<=left or lower<=upper:
                continue
            crop = image.crop((left,upper,right,lower))
            data = pytesseract.image_to_data(
                crop,config='--psm 7',output_type=pytesseract.Output.DICT)
            counters['ocr_passes'] += 1
            for index,word in enumerate(data['text']):
                if str(word).strip().strip('.,:;!') != label:
                    continue
                try:
                    confidence = float(data['conf'][index])
                except (TypeError,ValueError):
                    continue
                if confidence<40:
                    continue
                w,h = int(data['width'][index]),int(data['height'][index])
                if w>1 and h>1:
                    matches.append((left+float(data['left'][index])+w/2,
                                    upper+float(data['top'][index])+h/2))
    return matches[0] if len(matches)==1 else None


def tavi_dom_target(page,label,counters):
    from tavi_browser_snapshot import capture_controls
    from tavi_observe import dispatch
    snapshot = capture_controls(page)
    counters['dom_captures'] += 1
    packet = dispatch(snapshot,[dict(
        task='Identify fixture control',target=label,role='button')])
    counters['dom_resolutions'] += 1
    route = packet['routes'][0]
    if route['route']!='host_control':
        return None
    candidate = route['control'].get('candidate')
    if not isinstance(candidate,dict):
        return None
    bounds = candidate.get('bounds')
    if not isinstance(bounds,list) or len(bounds)!=4:
        return None
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in bounds):
        return None
    return (candidate['id'],candidate['label'],candidate['role'],
            candidate['context'],tuple(bounds))


def step(page,label,variant,counters):
    if not is_fixture(page):
        return False,'unexpected_page'
    target = screen_ocr_target if variant=='screenshot_ocr' else tavi_dom_target
    before = target(page,label,counters)
    if before is None:
        return False,'target_not_found_or_ambiguous'
    # Same freshness policy, independent observation per approach.
    current = target(page,label,counters)
    if current is None:
        return False,'reobserve_failed'
    if variant=='screenshot_ocr':
        if math.dist(before,current)>6:
            return False,'screen_location_changed'
        x,y = current
    else:
        if before!=current:
            return False,'host_identity_changed'
        if before[1]!=label or before[2]!='button':
            return False,'host_role_or_label_mismatch'
        x,y,w,h = current[4]
        x+=w/2
        y+=h/2
    if not is_fixture(page) or not (0<=x<1100 and 0<=y<700):
        return False,'host_provenance_or_bounds_changed'
    # EXACT same host action mechanism for both variants.
    page.mouse.click(x,y)
    counters['clicks_attempted']+=1
    return True,None


def trial(browser,workflow,labels,variant,repeat):
    context = browser.new_context(viewport={'width':1100,'height':700},
                                  device_scale_factor=1,service_workers='block')
    counters=Counter()
    try:
        page=context.new_page()
        page.route('**/*',lambda route:route.abort())
        page.set_content(fixture(labels),wait_until='load')
        if not is_fixture(page):
            raise RuntimeError('Fixture provenance check failed')
        began=time.perf_counter()
        completed=0
        failure=None
        for index,label in enumerate(labels):
            good,failure=step(page,label,variant,counters)
            if not good:
                break
            desired=('Verified complete' if index==len(labels)-1
                     else 'Next stage ready')
            # Common outcome oracle only, never used to find controls.
            if page.locator('#phase').inner_text(timeout=2000)!=desired:
                failure='outcome_mismatch'
                break
            completed+=1
            counters['verified_steps']+=1
        success=(completed==len(labels) and
                 page.locator('#phase').inner_text()=='Verified complete')
        return dict(workflow=workflow,variant=variant,repeat=repeat,
                    success=success,completed_steps=completed,
                    elapsed_ms=round((time.perf_counter()-began)*1000,3),
                    error_code=None if success else (failure or 'incomplete'),
                    counters=dict(counters))
    except Exception as exc:
        # Only exception class, not any possibly private exception text.
        return dict(workflow=workflow,variant=variant,repeat=repeat,
                    success=False,completed_steps=0,elapsed_ms=None,
                    error_code='exception_'+type(exc).__name__,counters=dict(counters))
    finally:
        context.close()


def percentile(values,portion):
    if not values:return None
    values=sorted(values)
    return round(values[math.ceil(len(values)*portion)-1],3)


def wilson(successes,n):
    if not n:return None
    z=1.96
    p=successes/n
    denom=1+z*z/n
    center=(p+z*z/(2*n))/denom
    half=z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/denom
    return [round(max(0,center-half),4),round(min(1,center+half),4)]


def summarize(rows):
    results={}
    for mode in MODES:
        entries=[r for r in rows if r['variant']==mode]
        completed=sum(r['success'] for r in entries)
        durations=[r['elapsed_ms'] for r in entries if r['elapsed_ms'] is not None]
        counts=Counter()
        for e in entries:counts.update(e['counters'])
        results[mode]=dict(
            tasks=len(entries),completed=completed,
            success_rate=round(completed/len(entries),4) if entries else None,
            success_wilson_95=wilson(completed,len(entries)),
            median_task_ms=round(statistics.median(durations),3) if durations else None,
            p95_task_ms=percentile(durations,.95),
            counters=dict(counts),
            failure_codes=dict(Counter(r['error_code'] for r in entries
                                       if r['error_code'])))
    pairs={}
    for item in rows:
        pairs.setdefault((item['workflow'],item['repeat']),{})[item['variant']]=item
    matched=[(item['screenshot_ocr'],item['tavi_dom']) for item in pairs.values()
             if set(item)==set(MODES)]
    measured=[(a,b) for a,b in matched if a['elapsed_ms'] is not None
              and b['elapsed_ms'] is not None]
    ratios=[a['elapsed_ms']/b['elapsed_ms'] for a,b in measured
            if b['elapsed_ms']>0]
    results['paired']=dict(
        pairs=len(matched),
        both_succeeded=sum(a['success'] and b['success'] for a,b in matched),
        measurable_pairs=len(measured),
        median_paired_latency_ratio=round(statistics.median(ratios),3)
              if ratios else None,
        median_paired_delta_ms=round(statistics.median(
              a['elapsed_ms']-b['elapsed_ms'] for a,b in measured),3)
              if measured else None,
        provider_input_tokens=None,provider_output_tokens=None,
        provider_cost=None,hosted_model_calls=0)
    return results


def run(*,repeats=3):
    if type(repeats) is not int or not 1<=repeats<=10:
        raise ValueError('repeats must be an integer 1..10')
    from playwright.sync_api import sync_playwright
    rows=[]
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True)
        try:
            for repeat in range(repeats):
                for name,labels in TASKS.items():
                    order=MODES if repeat%2==0 else MODES[::-1]
                    for mode in order:
                        rows.append(trial(browser,name,labels,mode,repeat))
        finally:
            browser.close()
    return dict(
        format='tavi-matched-screenshot-ocr-vs-dom-v1',
        scope='4 fixed generated 3-step browser workflows with real Chromium screenshot+Tesseract OCR or Tavi DOM; no external websites, no autonomous model',
        protocol=dict(workflows=list(TASKS),steps_per_task=3,repeats=repeats,
            alternating_order=repeats>1,
            isolated_new_context_every_trial=True,
            both_variants_reobserve_before_action=True,
            action_backend='same Playwright page.mouse.click',
            common_oracle='DOM result verifier, never used for target finding',
            timing='after page fixture setup; includes all observation, rechecks, clicks, verification'),
        summary=summarize(rows),trials=rows,
        hosted_llm_calls=0,actual_model_tokens_measured=False,
        real_external_websites_tested=False,
        full_autonomous_agent_compared=False)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repeats',type=int,default=3)
    parser.add_argument('--output',type=Path,
                        help='New JSON artifact: exclusive creation, no overwrite')
    args=parser.parse_args(argv)
    report=run(repeats=args.repeats)
    if args.output:
        with args.output.open('x',encoding='utf-8') as file:
            json.dump(report,file,indent=2)
            file.write('\n')
    print(json.dumps({k:v for k,v in report.items() if k!='trials'},indent=2))
    return 0 if all(report['summary'][m]['completed']==report['summary'][m]['tasks']
                    for m in MODES) else 1


if __name__=='__main__':
    raise SystemExit(main())
