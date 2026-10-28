# Tavi neural v1

## Identity and intended use

Original NumPy model trained from random initialisation for this user's Codex routing workflow. 408,056 trainable parameters; 1,518,495-byte compressed weights. No pretrained parameters, Laya calls, hosted language-model inference or GPU are required for prediction.

Predicts workload tier, relevance of147 named initial skills, and whether external skill discovery is appropriate. Host policy maps the learned tier to an available commercial model and supported reasoning setting. Source inspection/download decisions additionally use transparent deterministic gates; the neural network does not prove source safety.

## Architecture

Train-fitted TF-IDF vocabulary (up to4096 word, bigram and character-trigram features), normalised dense vector, shared tanh hidden layer of96 units, four-way softmax workload head,147 sigmoid skill heads and one sigmoid external-discovery head. Adam optimiser,240 epochs, seed20261028. Numeric NumPy arrays load without pickle and are checked against a SHA256 in model.json. This detects corruption; it is not a publisher signature.

## Data provenance

Exact dataset:dataset.json, SHA256 ba6356f939e8895d5f41c2098986fc7a49824ff7a0b05b10fe593c592969d420.

392 training rows and45 validation rows. Original agent-authored task paraphrases cover30 common skills, model tiers, ambiguity/no-skill tasks and external discovery. Additional weak positives come from deployment-visible installed skill descriptions, each labelled only for its skill; tier labels are masked for these rows. Those descriptions remain attributable to their upstream skill authors. No labelled user outcomes or measurements of commercial-model task performance are used.

Vocabulary, IDF and weights fit training rows only. Validation chooses skill threshold0.20 and external threshold0.70. Temperature remains1; no real-world probability calibration is claimed. training-report.json records losses and hashes. Retraining from dataset.json reproduced the exact weights hash on this PC.

## Frozen synthetic acceptance

50 cases were authored in training/heldout.py before training and never imported by the trainer. Exact train/validation/test prompt overlap is checked. Training and test share an author and domains, so paraphrase similarity and author bias can inflate results. This is not independent or field evaluation.

| Measure | Result |
|---|---|
| Workload-tier accuracy | 48/50 (96%) |
| Always-balanced tier baseline | 36/50 (72%) |
| Expected skill in top3, skill-labelled cases | 31/31 (100%) |
| Selected skill precision | 30/34 (88.2%) |
| Selected skill recall | 30/31 (96.8%) |
| No selected skill on no-skill cases | 16/19 (84.2%) |
| External-discovery classification | 49/50 (98%) |

Predeclared development gates: tier accuracy>=0.75, recall@3>=0.75, external accuracy>=0.85. All pass. evaluation.json retains every result, including errors. These results do not establish that selected commercial models solve tasks faster, cheaper or better.

## Known failures and boundaries

- A concise tooltip request predicted balanced rather than the authored fast label and fell below the skill threshold, though ux-writing ranked first.
- An ordinary Python-package installation explanation predicted fast rather than the authored balanced label.
- An installed-skill lookup falsely triggered external search.
- Three no-skill-labelled cases selected an extra skill.
- Adding an arbitrary marker and tool restrictions to a greeting caused ambiguity and withheld launch. The short greeting correctly selected the fast model and completed a live CLI launch.
- Only30 skills have richer examples; the rest rely on weak metadata positives. New skill names need retraining for learned selection.
- Not a general language model, calibrated Jev replica, malware detector or complete interpreter of user policy. Unfamiliar language and compound tasks can be misclassified.

## Artifacts

weights.npz SHA256:22e0f8b448bee5e0fbfbfb97f9ece31291d3406e11c025679d09a5ca65206482.

model.json contains architecture, thresholds, vocabulary and checksum. tavi_model.py implements inference/training. train_tavi.py retrains on CPU. evaluate_tavi.py reproduces acceptance. Reported inference timing excludes CLI catalog refresh, startup and internet access.
