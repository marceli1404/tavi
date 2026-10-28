# Tavi

Tavi v0.5 is a custom CPU decision model for choosing Codex workload tiers, installed skills, and whether to search for an external skill. Its own saved weights are the default backend. It is a specialised classifier, not a conversational language model or a demonstrated equivalent of Jev.

## Quick start

Requires Python 3.12+ and NumPy 2.x. Install dependencies with `python -m pip install -r requirements.txt`. Raw model inference needs no Codex, Node, Laya, GPU, API key or network:

```powershell
python tavi.py predict "Fix a mobile navigation menu"
```

From another folder, use the absolute path to tavi.py. For live Codex integration, copy tavi.config.example.json to tavi.config.json. Configure local skill roots and preferred model IDs.

For routing against the live Codex CLI catalog and installed skill inventory:

```powershell
python tavi.py inventory
python tavi.py route "Fix a mobile navigation menu" --plan
python tavi.py route "Explain this parser" --model gpt-6.1-sol --skill naming-convention
python tavi.py route "Say hello" --execute
```

Routing requires an installed Codex CLI; no paid-model inference occurs unless --execute is passed. --plan emits argv and stdin only. --execute starts a NEW read-only CLI task using normal Codex usage; it does not change the model of the current desktop conversation. A live greeting launch using Tavi-selected gpt-6-luna/low has succeeded. This is a launch check, not proof of complex coding-task quality.

The model learns a workload tier (fast, balanced, deep, review). Configured role lists map that tier to a visible model; reasoning settings map to supported low/medium/high levels. This is a transparent policy map, not empirical performance ranking of commercial models. Missing role models, weak vocabulary coverage, ambiguous predictions, or unavailable required policy skills withhold execution.

--model preserves an explicit model choice. --skill pins an installed skill by unique name or ID. Skill mentions in a launch prompt do not disable other mandatory host rules. Inventory reflects files on disk and CLI-visible models; it is not proof that a host exposes every plugin skill or that every model accepts inference.

## Codex skill

Copy `codex-skill` to your Codex skills directory as `tavi-decision`, then edit its installation path to point to this checkout. Invoke `$tavi-decision` after skill discovery refreshes. It provides routing advice; the calling agent must still follow your complete workflow instructions. The example configuration does not impose the original developer's personal skill policy.

## Routing controls, health and batches

```powershell
python tavi.py route "Fix a mobile layout" --preference quality --exclude-model gpt-6-astra --plan
python tavi.py route "Fix a mobile layout" --preference speed --exclude-skill layout-grid
python tavi.py doctor
python tavi.py refresh
python tavi.py refresh --activate
python tavi.py rollback
python tavi.py batch tasks.json --output results.json
```

Preferences are explicit policy choices: auto follows the learned workload tier, speed uses the configured fast role/low reasoning, quality uses the deep role/high reasoning. These are not measured price or latency guarantees. An explicit --model takes precedence. Preferences never force an ambiguous task to execute. Exclusions must identify available models/skills; conflicting explicit or required-policy skills produce errors. The explanation object keeps the learned prediction, preference, exclusions and policy selections distinct.

Doctor checks weight integrity, required skills and newly added, removed or changed skill metadata. It does not train or call external models. Refresh trains a NEW CPU candidate from current installed metadata, retaining existing weights. Activation is opt-in and requires acceptance gates plus no drop greater than0.02 in tier accuracy, top3 recall, selected precision/recall, no-skill accuracy or external accuracy versus the active model. Repeated use of the synthetic acceptance set for development is not independent evaluation. Candidate reports/logs remain available even on rejection. Config changes during training prevent stale activation. A snapshot allows rollback of the model pointer while preserving other current preferences/policies.

The v2 model now learns Tavi's own skill using a separate trained classifier while freezing the accepted v1 computations. Auto refresh expands new labels when existing metadata is unchanged; --strategy full requests a complete retrain. Added labels require validation and acceptance cases; metadata alone cannot justify activation. A current catalogue makes refresh a no-op. The original v1 model and rollback snapshots are preserved. Refresh is not guaranteed to produce an acceptable replacement.

Batch input is a JSON array of1–256 task strings or objects. Objects support id, prompt, model, skills, preference, exclude_models and exclude_skills. Batch loads the inventory/model once, reports errors per entry and never executes tasks. Output files must be new; existing results are preserved. See Features-v0.3.md for examples and verification.

## Discover and inspect external skills

```powershell
python tavi.py discover "blender"
python tavi.py review-skill openai/skills skills/.system/skill-creator/SKILL.md --task "Create a reusable local skill"
```

Search covers public GitHub repository names, descriptions and README content; it does not search all internet skills or authenticated code. Results are leads, not endorsements.

Source review pins a commit, inspects all files within the requested skill directory up to 40 files/512 KB, verifies Git blob hashes, checks duplicate names, records repository/skill licence evidence, reports Python dependency and runtime hints, and flags selected suspicious patterns. Unreviewable binaries, symlinks, truncated trees or oversize sources fail closed. Static checks do not establish trust, full runtime compatibility, legal permission or absence of malicious behaviour.

`review-skill --stage NEW_DIRECTORY` downloads passive source for inspection. It never installs or executes it and refuses configured active skill directories or existing staging directories. Download recommendations still require source review; Tavi's external-search score is not installation permission.

## Local outcomes and retraining

`route --record` opts into saving the complete task and decision under ignored data/decisions. Default routing does not save task text. After explicit execution, recording also saves the process exit code separately; a zero exit code is not automatically a verified task outcome.

```powershell
python tavi.py feedback DECISION_UUID --tier balanced --skill responsive-design --outcome unverified --evidence "Observed routing; task result not checked"
python train_tavi.py --dataset models/tavi-v1/dataset.json --output models/retrained
python evaluate_tavi.py --model models/retrained
python -m unittest -v
```

Feedback appends local events, preserving the original decision. Use --external for a labelled external-search case. Labels and outcome notes are operator-entered, not automatically verified ground truth. `train_tavi.py --feedback data/feedback --output models/next` explicitly incorporates them. No silent online training occurs. Do not feed acceptance cases into training; evaluation checks exact prompt overlap and fails on leakage. Retraining should use a new output directory so the accepted model remains recoverable.

## Evidence and limits

ROUTER-8 now includes24 actual model requests on eight pinned public HumanEval tasks, plus Tavi/Laya routing replay with latency, token usage and abstentions preserved. Use `python tavi.py benchmark` to read saved results without making hosted calls. ROUTER-9 adds `desktop status`, `desktop selftest` and guarded `desktop switch` commands. Next-turn model updates are verified on an owned ephemeral thread; the desktop control socket on this PC remains unavailable, so current-desktop switching is not claimed. See Features-v0.5.md for results, reproducibility commands and limitations.

See models/tavi-v2/Model-Card.md and Features-v0.4.md for the current412153-parameter expanded model, and models/tavi-v1 for the frozen408056-parameter base. The base was trained from scratch on392 synthetic/weak-metadata training rows and45 validation rows. The added classifier uses412 training/51 validation rows and preserves the base computations. Original50-case results remain96% tier accuracy,100% skill recall@3,88.2% selected precision and98% external accuracy; a separate20-case synthetic set verifies the new skill. These are development measurements, not independent real-world accuracy or calibrated confidence.

The current model has148 skill outputs;30 base skills and the new Tavi label have richer authored examples. New skills can be added through guarded expansion; existing metadata changes can require full retraining. Scores can be overconfident, extra instructions can change routing, and domain coverage is limited. Prefer short task descriptions and review results. The original Laya baseline remains available with `route --backend laya` when configured; it is never an automatic fallback. Raw predict uses models/default-model.json without needing local config, Codex or Laya.

Official integration references: [Codex CLI flags](https://learn.chatgpt.com/docs/cli/reference), [Codex skill invocation](https://learn.chatgpt.com/docs/build-skills), [GitHub repository search](https://docs.github.com/en/rest/search/search), [GitHub tree inspection](https://docs.github.com/en/rest/git/trees). Training/evaluation keeps fitted transformations separate from acceptance data, following [data-leakage guidance](https://scikit-learn.org/stable/common_pitfalls).

## Licence

Original Tavi source, synthetic examples and trained weights are released under the MIT licence; see [LICENSE](LICENSE). Third-party benchmark material retains its own licence; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Tavi is an independent project and is not affiliated with OpenAI or Laya.
