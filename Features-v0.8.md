# Tavi v0.8 — Broader task routing and desktop-control recheck

## ROUTER-14

A tier-only residual classifier improves task-description routing while preserving every original array and all skill/external scores exactly on804 development examples.1053 training/205 validation rows use original tier labels plus new authored descriptions. No HumanEval task or previous calibration-check label is added to the training corpus. Epoch and correction gate use validation only.

Five candidate attempts and their failures are retained locally: first lost old accuracy/public coverage; second missed the historical check gate; third improved that gate but lost public coverage; fourth broadly preserving old recommendations missed the historical gate. The final policy preserves confident base choices specifically for explicit Python function specifications when the adapter would newly abstain. Development sets guided these changes and are not claimed as blind independent tests.

The final candidate passes all predefined development gates: old50 tier accuracy96% retained; development40 accuracy75→95%; historical32 accuracy56.25→78.125%; development public8 coverage8/8 retained. A separate32-case authored audit and eight additional public tasks were fixed after the final weights/metadata were frozen. Audit policy accuracy68.75→93.75%; public coverage stays4/8 in both. The latter is a material remaining gap.

Two fixed public outcome tasks, HumanEval31 and112, received one completion each from fast/balanced/deep configurations: six total hosted requests. All six outputs pass upstream tests; the selected routes pass2/2 in both versions. These two cases were fixed before training, never fitted, and not replaced after results. No superiority, dollar-cost, or broad real-world accuracy claim follows. Saved answers reproduce through the bounded judge; source licence is preserved.

The attempted new calibration fails its unchanged check gates and is not activated. New-model probabilities remain explicitly uncalibrated. The calibrated v2 copy remains intact. INT8 export of the new adapter is refused until validated. Accepted v3 activation verifies both weight hash and exact metadata signature because two candidates can share weights but differ in correction policy. Full refresh cannot silently discard the adapter; skill expansion preserves it. Rollback keeps the previous local config.

## ROUTER-9

Rechecked on28 October2026: installed CLI0.162.1, desktop-bundled CLI0.165.0-alpha.1.2. Both supported proxy paths fail to reach a desktop control socket. Daemon version check also reports unavailable. The newer bundled executable successfully changes model/effort on an owned ephemeral stdio thread and verifies the notification, with no generation. It does not change a desktop-owned chat.

Official lifecycle/control documentation: https://learn.chatgpt.com/docs/app-server . Native app tools expose no direct setting action for this running chat. Starting another server, changing stored thread files, or sending an unsolicited follow-up message would not verify direct control of this desktop actor. No desktop state or security settings changed. ROUTER-9 remains waiting for a supported bridge.

Local v0.8 includes source, v1/v2/v3 model copies, test corpora and saved evidence. No GitHub push or website change is part of this continuation.

The historical eight-task routing check improves6/8→7/8 covered routes, with all seven selected saved outputs passing. This reuses existing historical completions and is separate from the six fresh generations. HumanEval132 still abstains; no outcome prompt or label was fitted.
