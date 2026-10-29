<p align="center"><img src="assets/tavi-logo.svg" width="340" alt="Tavi"></p>

# A small model. A clearer start.

Tavi v0.16 is an open-source CPU model that recommends a workload tier, a Codex model and reasoning level, installed skills, and whether to look for another skill. An optional hybrid screenshot helper combines local Windows OCR with Codex vision.

Tavi is a specialised classifier. Its role-to-model mapping is explicit policy, not a measured ranking of commercial models.

Current target model: failed real-screen confidence validation. The95% policy remains configurable, but this model requires review and cannot qualify probability-based automatic actions. See [Features-v0.14.md](Features-v0.14.md) for measured local speed, recognition failures, coding outcomes and remaining gaps.

## Install

Requires Git and Python 3.12+. Offline prediction needs NumPy, but no GPU, Codex login, API key or network.

```sh
git clone https://github.com/marceli1404/tavi.git
cd tavi
python -m venv .venv
```

Activate the environment with `.venv\Scripts\Activate.ps1` on Windows or `. .venv/bin/activate` on macOS/Linux, then:

```sh
python -m pip install -r requirements.txt
python tavi.py predict "Fix a mobile navigation menu"
```

For one-line installers, visit [tavi.marceli.tech](https://tavi.marceli.tech/#install). They create a new folder and preserve existing skills.

## Connect Codex

Install and log into the Codex CLI separately. Copy `tavi.config.example.json` to `tavi.config.json`, set your skill directories and preferred model IDs, then:

```sh
python tavi.py inventory
python tavi.py route "Fix a mobile navigation menu" --plan
python tavi.py doctor
```

Copy `codex-skill` to your Codex skills directory as `tavi-decision`, and set the checkout path in its instructions. Invoke `$tavi-decision` after skill discovery refreshes. The calling agent must still follow your complete workflow instructions.

`--plan` does not run a hosted task. `route --execute` starts a separate read-only Codex CLI task using account usage. Switching the current desktop chat's model still requires a supported bridge, which remains unavailable.

## Screenshots: local and hosted

```sh
python -m pip install -r requirements-vision.txt
python tavi.py vision screen.png --task "Read the screen" --mode local
python tavi.py vision screen.png --task "Locate Install" --target Install
python tavi.py vision screen.png --task "Find the settings control" --execute --cache output/screens
```

Local mode uses installed Windows OCR language models and sends nothing to Codex. Hybrid mode locates one unique exact OCR word locally; ambiguous screens need `--execute` for hosted interpretation. Other platforms can use Codex vision with the existing CLI login. Tavi does not capture the desktop or perform clicks. Results are observations and candidate coordinates for a computer-use agent to verify against the current screen.

The opt-in cache stores recognized screen text and observations locally for 300 seconds by default. It reuses identical image/task/model/settings inputs. Read [the screenshot guide](Features-v0.10.md) for coordinates, platform requirements, actual smoke-test timings and limitations. Screenshot support adds Pillow; the core router still needs only NumPy.

## Skills and routing controls

```sh
python tavi.py discover "blender materials"
python tavi.py discover "blender" --provider github
python tavi.py review-skill openai/skills skills/.system/skill-creator/SKILL.md --task "Create a reusable skill"
python tavi.py route "Review this parser" --preference quality --plan
python tavi.py route "Explain a function" --model gpt-6.1-sol
python tavi.py batch tasks.json --output results.json
```

Discovery searches [AwesomeSkill sorted by stars](https://awesomeskill.ai/search?sort=stars) first, ranking task relevance before popularity. Results are leads, not endorsements. Source review pins a commit and checks hashes, licences, dependencies, duplicates and selected static risks. `--stage NEW_DIRECTORY` saves passive source only; it does not install or run a skill.

`doctor` checks model integrity and skill drift. `refresh` builds an isolated candidate, and `refresh --activate` requires acceptance checks before changing the model pointer. `rollback` restores a saved previous pointer when available. Explicit preferences, exclusions and skill choices remain visible policy.

## Evidence and limits

The accepted v4 clean model has 440817 parameters and 148 skill labels. It preserves earlier skill/external-search heads and ordinary-text tier outputs. Its isolated code head improves historical public coding coverage to 8/8, while a separate difficult audit still has 2/8 abstentions. Public benchmark tasks may be memorized by hosted models; these small checks do not establish general task quality or the best model.

Calibration is partial and based on authored synthetic labels. Code-context tier check accuracy is 22/36 (61.11%); plain-text tier and code-context external scores remain raw. Skill scores are not calibrated probabilities. These outputs do not predict task success. INT8 experiments made saved weights smaller but were slower on the tested NumPy setup and changed six skill selections; FP32 remains the default.

- [v0.10 hybrid screenshots](Features-v0.10.md)
- [v0.9 code adapter and partial confidence](Features-v0.9.md)
- [v0.8 tier coverage](Features-v0.8.md)
- [v0.7 probability and quantization](Features-v0.7.md)
- [v0.6 AwesomeSkill discovery](Features-v0.6.md)
- [Accepted model card](models/tavi-v4-clean/Model-Card.md)

## Verify and contribute

```sh
python -m unittest -q
python tavi.py benchmark
python bundle_tavi.py
```

Tests and saved-report inspection do not launch hosted generation. Install optional screenshot requirements to include all vision tests. The benchmark judge is bounded test execution, not a general malware sandbox. Keep credentials, local configuration, screenshots and private recordings out of commits. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

Original source, synthetic examples, trained weights and Tavi artwork use the [MIT licence](LICENSE). Third-party benchmarks retain their notices; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Tavi is independent and is not affiliated with OpenAI or Laya. Optional dependencies and hosted services have their own terms.

## Compact target review in v0.11

Use `python tavi.py propose screenshot.png --task "Press Go" --target Go` for a local target-match percentage and a compact packet for the current Codex agent. This avoids sending an image or starting a second hosted call by default. The agent reviews, verifies the current UI, performs the authorized action and checks its result. `--execute` requests an optional headless text-only review; it was slower than direct image interpretation in the small comparison. Percentages are synthetic-layout estimates, not action-safety or field-success probabilities. See [Features-v0.11.md](Features-v0.11.md) and [the target model card](models/screen-target-v1/Model-Card.md).

## Warm local computer-use sessions

Use `python tavi.py propose-stream` for repeated local screenshot-to-target proposals without restarting Windows OCR. Each JSON-line image/task/target request gets a fresh proposal; no hosted calls or actions occur in the stream. Close stdin when work ends. The12-image local comparison measured468ms one-shot versus61ms warm. Startup and full-agent timing limits are in [Features-v0.12.md](Features-v0.12.md).

## 95% automatic routine buttons

The optional automatic-button policy uses raw target confidence >=95%, existing proposal checks and trusted live host verification. The supported host driver performs the click and checks its result. The OCR process only returns eligibility; it cannot click. Portable configuration is disabled until its owner opts in. See [Features-v0.13.md](Features-v0.13.md) for the callback contract, no-retry behavior and synthetic-confidence limits.


## Claude Code provider

Install and sign in to the official Claude Code CLI separately. Tavi never
asks for your credentials. Run `python tavi.py provider-status claude --auth`
for availability, version and redacted sign-in status. The integration requires
Claude Code 2.1.259 or newer; 2.1.312 was checked locally. If the CLI is not on
PATH, set `claude_cli` to its executable or Node entrypoint in your private
configuration. A null value uses normal CLI discovery.

```bash
python tavi.py inventory --provider claude
python tavi.py route "Review this parser" --provider claude --plan --workspace .
python tavi.py route "Fix this parser" --provider claude --interactive --plan --workspace .
```

Fast/balanced/deep map to the official haiku/sonnet/opus aliases by default.
These are configurable policy choices, not measured model rankings or proof
of account access. Codex model settings stay separate. A review-needed route
withholds its launch plan. `--plan` never starts a hosted task.

Add `--execute` only when ready to launch. Default Claude execution uses print
planning mode with Read/Glob/Grep, MCP tools disallowed and permission prompts
disabled. This limits CLI tools; it is not an operating-system sandbox.
`--interactive --execute` opens a full native Claude session in a real terminal,
with its normal permissions and approval flow. It can edit code within the
request; Tavi supplies no permission bypass. Claude uses your own account and
allowance. Local tests verified argument parsing and unauthenticated refusal;
an authenticated hosted request has not yet been verified.

## Exact control facts before image inference

When your supported browser or native driver already exposes the intended
control, use that evidence before OCR. `target-controls` accepts a local
`tavi-control-snapshot-v1` JSON inventory supplied by that host:

```bash
python tavi.py target-controls controls.json --task "Inspect Skills" --target Skills
```

Use `--context` to require an exact group label for duplicate controls. Matching
normalizes case and whitespace, and checks role, visibility, enabled state,
viewport geometry and five-second freshness. Missing or ambiguous matches
require review. `--offline` permits replay only and is never actionable.

The result carries an identity and snapshot/task hashes, **not a probability
or permission to click**. Snapshot fields are untrusted claims until the host
rechecks the current control and authorization. The supported host performs
any action and verifies its result. Tavi adds no capture or input backend.
See `Features-control-grounding.md` for the schema and measured limits.


## Review coverage across several skills


`python tavi.py coverage-review REQUEST.json` builds an offline review packet
for the current Codex chat. It retains the full task context and checks every
operation, including coverage shared across skills. Add `--answer ANSWER.json`
to validate a response against the same task/inventory snapshot. `-` accepts
JSON through stdin without recording a task file. This command makes no model
or network request and grants no installation or execution permission.
See `Features-coverage-review.md` for the schema, examples and measured limits.
