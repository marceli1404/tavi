# Contributing

Install Python 3.12+ and dependencies with `python -m pip install -r requirements.txt`. Run `python -m unittest -q`, `python tavi.py predict "Say hello"`, and `python tavi.py benchmark`. These commands need no hosted model requests.

Keep private configuration, task recordings, credentials and raw CLI logs out of commits. Describe behaviour changes and the checks performed in pull requests. Preserve model rollback paths and evaluation separation. Do not train on held-out outcome benchmarks or lower acceptance gates just to improve published scores. Hosted outcome benchmarks consume account usage and should be run deliberately.

Public issues are suitable for ordinary bugs and feature requests. Do not put credentials or personal data into an issue.
