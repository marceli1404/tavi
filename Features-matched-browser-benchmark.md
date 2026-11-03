# Matched browser computer-use comparison: methodology and scope

This evaluation compares **two observation and target-finding routes**, not two
full autonomous agents. It runs on a real, locally launched headless Chromium
browser. The browser visits **only generated HTML on \`about:blank\`**. No real
third-party websites, credentials, host sessions, purchases, messages, external
network requests, generative planning models or cloud API calls are used.

## Pre-registered tasks

Four three-step deterministic workflows:
- Onboarding: Begin → Continue → Finish
- Settings: Settings → Alerts → Save
- Auditing: Audit → Check → Report
- Catalog: Find → Filter → Open

The label sequence is provided as a fixed task plan to **both** routes.
No model reasons about which button to click. Each workflow starts from a
fresh browser context with identical viewport, HTML, JavaScript and action
permissions. Trial order alternates by repetition.

## The two routes

- **Screenshot-first baseline:** Playwright screenshot; pixel-only dark-outline
  rectangle proposal; Tesseract OCR of candidate regions; exact label match;
  fresh screenshot and OCR immediately before any click. It **does not** use
  browser DOM/accessibility metadata to find targets.
- **Tavi DOM-first:** \`capture_controls(page)\` and \`dispatch(snapshot,query)\`;
  allow only unique exact host-control route; fresh independently captured
  control snapshot immediately before acting; require unchanged
  ID/label/role/context/bounds.
- **Both:** Same \`page.mouse.click(x,y)\` host executor; same independent DOM
  **result verifier** after every action. Neither can click outside its
  generated, internally tagged fixture.

The verifier is shared, but neither route can read it when deciding where to
click. Both make exactly three authorised clicks on a successful workflow.

The screenshot baseline uses genuine local Tesseract OCR, not a mocked
callback. The DOM route uses real Chromium page observations. Real screenshots
are never written to disk; only numeric counters such as screenshot bytes
are retained.

## Metrics

The experiment records *each* trial's completion, verified steps, task
elapsed time, failure category, screenshot count/bytes, OCR passes and DOM
captures. Task timing starts after generated page loading, and includes
observation, a second fresh verification, all mouse clicks and result checks.
It excludes browser launch, context/page initialization, and initial fixture
load. Summary includes success rate with Wilson 95% confidence interval,
task median/p95 latency and median **paired** latency ratio/difference.

Model input/output tokens and model costs are **unknown/not applicable**:
there are no hosted model calls, and Tavi's local deterministic router is not
equivalent to a general agent planner. The output uses explicit
\`actual_model_tokens_measured=false\`, not invented savings.

## Reproduce

In a Python 3.12 environment on Linux:

\`\`\`bash
python -m pip install -r requirements.txt -r requirements-browser-eval.txt pytesseract==0.3.13
sudo apt-get install tesseract-ocr
python -m playwright install --with-deps chromium
python -m unittest -q test_matched_browser_workflows
PYTHONPATH=. python benchmarks/matched_browser_workflows.py --repeats 3 \
  --output matched-browser-results.json
\`\`\`

The source branch's GitHub Actions \`matched-browser-comparison\` job runs this
with actual Chromium and Tesseract and uploads the raw results as
\`tavi-matched-browser-results\`. The JSON file is written with exclusive
creation and is never silently overwritten.

## Important interpretation constraints

This is a controlled benchmark of observation efficiency and safe
step-by-step execution on simple, high-contrast local pages. It does **not**
measure natural-language planning, unexpected page design, cross-domain
navigation, credential handling, anti-automation defences, real-world
robustness, paid model tokens, or comparable task success against OpenAI,
Claude, OSWorld, BrowserGym or WebArena.

The rectangle detector deliberately benefits from these simple, outlined
buttons. That is acceptable for measuring a fixed baseline but is **not** a
general screenshot understanding system. Tavi is not a production-authorised
general click backend. A larger, consented, stratified external-task study
with the **same real agent model and executor**, both provider usage records
and independently checked outcomes would be required for claims about
end-to-end commercial agent speedups or superiority.

If one route fails, its failure remains in the summary. Do not compare only
the completed subset. A ratio based on a handful of synthetic tasks is
descriptive, not causal proof of performance across the open web.
