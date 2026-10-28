# Tavi v0.5 — measured outcomes and model-switching protocol

## ROUTER-8: externally authored outcome evaluation

Eight tasks from [OpenAI HumanEval](https://github.com/openai/human-eval) were fixed before any model requests:0,20,56,70,100,132,146,154. Source commit b9453e8f1865df0a0057a1383767caa400acfbcf; original compressed dataset SHA256 b796127e635a67f93fb35c04f4cb03cf06f38c8072ee7cee8833d7bee06979ef. MIT licence and selected prompts/tests/reference solutions are retained in benchmarks/humaneval. These examples were not added to Tavi training.

Each of three configured model/effort pairs received one request per task (24 total). Tests were withheld from generation and run locally. Upstream reference solutions all passed the restricted pure-function judge. Returned code was graded by assertions, not by another model. Stored returned solutions reproduce all22 available code verdicts; two requests did not return code within150 seconds.

| Requested model / effort | Verified successes | Wrong-code results | Generation timeouts | Median request seconds | Token usage observed |
|---|---:|---:|---:|---:|---:|
| gpt-6-luna / low | 7/8 | 1 | 0 | 4.74 | 8/8 |
| gpt-6.1-sol / medium | 8/8 | 0 | 0 | 7.70 | 8/8 |
| gpt-6-astra / high | 6/8 | 0 | 2 | 12.65 | 6/8 |

The fast model's bracket solution failed upstream assertions. The deep-model failures are generation timeouts; no wrong-code claim or root cause is inferred for them. One other deep request took123.25 seconds and succeeded. Wall times include the CLI and service latency. Input token counts also include each model's client-supplied context, not just the public problem. No solver tools were observed in the completed event logs.

Known input/output tokens: fast160062/744, balanced194061/905, deep122815/648 for its six reported requests. Timeout usage is unknown. These are usage observations, not equal-priced tokens or dollar charges. The signed-in plan does not provide a verified per-request dollar amount, so USD cost remains null.

## Tavi versus local Laya

Frozen router choices were replayed against the SAME measured outcome matrix; no second set of hosted requests was made. Laya used a published four-choice workload-tier question. Both used a0.5 score cutoff, which is not calibrated equivalently across these models. Tavi also retains its vocabulary-coverage guard.

| Router | Covered | Verified passes on covered tasks | Abstentions | Median warm CPU inference |
|---|---:|---:|---:|---:|
| Tavi | 6/8 | 6/6 | 2 | 1.09 ms |
| Laya | 8/8 | 7/8 | 0 | 765.01 ms |

On the SAME six covered tasks, both produced six verified successes. Selected generation time totals were35.60 seconds for Tavi and32.57 seconds for Laya, plus6.33 ms versus4604.18 ms of local routing. Known selected input tokens were124832 versus120413; both selected579 output tokens. Different-coverage totals must not be presented as a cost/speed win.

This is a small historical benchmark with possible foundation-model pretraining contamination, one completion per model/task and no statistical superiority claim. Independent authorship/executable outcomes improve on same-author policy labels, but do not establish real-world project quality or skill-selection accuracy. The accepted Tavi weights remain unchanged.

## Reproduce and inspect

```powershell
python tavi.py benchmark
python benchmarks/outcomes.py --limit 1 --run-dir output/new-small-outcome-run
python benchmarks/compare_routers.py --outcomes output/outcome-benchmark/report.json
```

The first command is read-only and uses saved reports. The second makes THREE hosted requests per uncached case (limit1–8). It defaults to one case; an8-case run makes24 requests. Reused caches require an unchanged dataset, model/effort specification, prompt and answer schema. Do not rerun hosted benchmarks casually near account limits. The original completed outcomes, returned code, run manifest and router comparison are packaged under benchmarks/results. Raw private CLI logs are not packaged. The judge has static restrictions and a subprocess timeout; it is not a general hostile-code sandbox.

## ROUTER-9: protocol supported, desktop bridge unavailable

The installed0.162.1 CLI's generated schema exposes thread/settings/update with model and effort overrides for subsequent turns. The [official app-server documentation](https://learn.chatgpt.com/docs/app-server) describes its transports and thread/turn lifecycle. The running desktop bundles0.165.0-alpha.1.2 and uses its own stdio app-server; no reachable default external control socket was found.

An owned stdio app-server created a disposable ephemeral thread, then Tavi's guarded adapter changed it from gpt-6-luna to gpt-6.1-sol/medium and verified thread/settings/updated. No generation was started and no desktop-owned thread was changed. This proves the protocol path in an owned thread, not automatic switching in the current desktop conversation.

```powershell
python tavi.py desktop status
python tavi.py desktop selftest
python tavi.py desktop switch --thread THREAD_ID --model gpt-6.1-sol --effort medium
```

Switch connects only through the supported proxy (optional --socket). It requires a visible model, supported effort and an already-loaded idle target. It never starts a turn, resumes a disk thread, interrupts current work or changes sandbox/approval settings. Missing confirmation is reported as unverified, not retried as a presumed success. Selftest owns and closes only its disposable server. Status correctly reports unavailable on this PC.

Automatic changes to THIS desktop conversation remain waiting for a supported reachable bridge. Starting an unrelated daemon or editing persisted thread state would not prove control over the desktop actor and is not offered as a substitute. No UI automation, private IPC patching, app restart or security changes were performed.

## Verification

64 tests cover all previous routing/training features, upstream judge references, wrong-code detection, disallowed code operations, unchanged benchmark-cache manifests, coverage-matched comparisons and guarded model updates. The bundle validates exact member hashes, native predictions, saved benchmark reporting and the complete test suite from fresh extraction without hosted calls.
