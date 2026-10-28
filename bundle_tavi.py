"""Build and verify a local source/model bundle; never uploads anything."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

BASE = Path(__file__).resolve().parent
ROOT_FILES = ['tavi.py', 'tavi_model.py', 'tavi_router.py', 'tavi_discovery.py', 'tavi_feedback.py',
              'tavi_health.py', 'tavi_batch.py', 'test_features.py', 'Features-v0.3.md',
              'tavi_expand.py', 'expand_tavi.py', 'evaluate_expansion.py', 'test_expansion.py', 'Features-v0.4.md',
              'tavi_appserver.py', 'test_outcomes_desktop.py', 'Features-v0.5.md',
              'train_tavi.py', 'evaluate_tavi.py', 'bundle_tavi.py', 'test_tavi.py', 'test_custom.py',
              'README.md', 'LICENSE', 'THIRD_PARTY_NOTICES.md', '.gitignore', 'CONTRIBUTING.md', 'requirements.txt', 'tavi.config.example.json']
MODEL_FILES = ['weights.npz', 'model.json', 'dataset.json', 'training-report.json', 'evaluation.json', 'Model-Card.md']


def main():
    files = ROOT_FILES + ['training/corpus.py', 'training/heldout.py', 'training/extensions.py', 'training/extension_heldout.py',
                          'codex-skill/SKILL.md', 'models/default-model.json']
    files += ['models/tavi-v1/'+name for name in MODEL_FILES]
    files += ['models/tavi-v2/'+name for name in MODEL_FILES+['extension-evaluation.json']]
    files += ['benchmarks/'+name for name in ['prepare_humaneval.py','judge.py','outcomes.py','compare_routers.py','laya_worker.mjs',
              'humaneval/cases.json','humaneval/provenance.json','humaneval/LICENSE',
              'results/report.json','results/router-comparison.json','results/run-manifest.json','results/model-answers.json','results/desktop-control.json']]
    payloads = {name: (BASE/name).read_bytes() for name in files}
    manifest = {name: hashlib.sha256(data).hexdigest() for name,data in payloads.items()}
    payloads['manifest.json'] = json.dumps(manifest, indent=2).encode()
    directory = BASE/'dist'
    directory.mkdir(exist_ok=True)
    archive = directory/'tavi-v0.5-source-and-model.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for name, data in payloads.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 28, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            bundle.writestr(info, data)
    with tempfile.TemporaryDirectory(prefix='Tavi bundle verification ') as folder:
        root = Path(folder)
        with zipfile.ZipFile(archive) as bundle:
            assert set(bundle.namelist()) == set(payloads), 'Archive membership differs'
            bundle.extractall(root)
        for name, digest in manifest.items():
            assert hashlib.sha256((root/name).read_bytes()).hexdigest() == digest, name
        # No copied local config, Codex inventory or Laya runtime is present in this extraction.
        run = subprocess.run([sys.executable, str(root/'tavi.py'), 'predict', 'Say hello'],
                             capture_output=True, text=True, encoding='utf-8', cwd=root, timeout=30)
        assert run.returncode == 0, run.stderr
        prediction = json.loads(run.stdout)
        assert prediction['tier'] == 'fast', prediction
        added = subprocess.run([sys.executable,str(root/'tavi.py'),'predict','Use Tavi to choose a model and skills for this task'],
                               capture_output=True,text=True,encoding='utf-8',cwd=root,timeout=30)
        assert added.returncode == 0, added.stderr
        assert json.loads(added.stdout)['skills'][0]['name'] == 'tavi-decision'
        assert not (root/'tavi.config.json').exists()
        report = subprocess.run([sys.executable,str(root/'tavi.py'),'benchmark'],capture_output=True,text=True,encoding='utf-8',cwd=root,timeout=15)
        assert report.returncode == 0, report.stderr
        assert json.loads(report.stdout)['models']['balanced']['passed'] == 8
        tests = subprocess.run([sys.executable, '-m', 'unittest', '-q'], capture_output=True,
                               text=True, encoding='utf-8', cwd=root, timeout=45)
        assert tests.returncode == 0, tests.stderr
    result = dict(path=str(archive), bytes=archive.stat().st_size,
                  sha256=hashlib.sha256(archive.read_bytes()).hexdigest(), files=len(payloads),
                  verification='Exact members and manifest hashes match; extracted independent predictions, saved benchmark report and all64 tests pass without hosted calls')
    (directory/'bundle-verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
