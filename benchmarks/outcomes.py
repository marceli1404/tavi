"""Measured public coding outcomes; no training, self-grading, or inferred prices."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
from tavi import codex_command

MODEL_ROLES=[('fast','gpt-6-luna','low'),('balanced','gpt-6.1-sol','medium'),('deep','gpt-6-astra','high')]
SCHEMA={'type':'object','properties':{'code':{'type':'string'}},'required':['code'],'additionalProperties':False}
PROMPT_PREFIX=('Implement the following Python function. Return the COMPLETE function and any necessary helper functions/imports in the code JSON field. '
               'Do not use tools, access files or include prose/markdown. Use only standard Python and typing/math/collections/itertools/functools/re if needed.\n\n')


def ensure_run_manifest(run_dir,dataset_sha256):
    expected=dict(dataset_sha256=dataset_sha256,model_roles=MODEL_ROLES,
                  prompt_sha256=hashlib.sha256(PROMPT_PREFIX.encode()).hexdigest(),
                  schema_sha256=hashlib.sha256(json.dumps(SCHEMA,sort_keys=True).encode()).hexdigest())
    # JSON round-trip normalises tuples so repeated runs compare consistently.
    expected=json.loads(json.dumps(expected))
    path=run_dir/'run-manifest.json'
    if path.exists():
        if json.loads(path.read_text(encoding='utf-8'))!=expected:
            raise ValueError('Benchmark specification changed; use a new run directory instead of reusing cached outcomes')
    else:
        previous=run_dir/'report.json'
        if previous.exists() and json.loads(previous.read_text(encoding='utf-8'))['dataset_sha256']!=dataset_sha256:
            raise ValueError('Existing outcomes belong to another dataset')
        path.write_text(json.dumps(expected,indent=2),encoding='utf-8')


def judge(code,case):
    request=dict(code=code,test=case['test'],entry_point=case['entry_point'])
    try:
        proc=subprocess.run([sys.executable,'-I','-S',str(BASE/'benchmarks/judge.py')],input=json.dumps(request),
                            capture_output=True,text=True,encoding='utf-8',timeout=4)
        return json.loads(proc.stdout) if proc.returncode==0 else dict(passed=False,result='judge_process_error')
    except subprocess.TimeoutExpired:
        return dict(passed=False,result='timed_out')


def generate(case,role,model,effort,run_dir):
    task_dir=run_dir/(case['task_id'].replace('/','_')+'-'+role)
    result_file=task_dir/'result.json'
    if result_file.is_file():
        return json.loads(result_file.read_text(encoding='utf-8'))
    task_dir.mkdir(parents=True,exist_ok=True)
    answer=task_dir/'answer.json'
    schema=run_dir/'answer-schema.json'
    schema.write_text(json.dumps(SCHEMA),encoding='utf-8')
    prompt=PROMPT_PREFIX+case['prompt']
    command=codex_command()+['exec','--model',model,'-c','model_reasoning_effort="'+effort+'"',
                            '--ignore-user-config','--ephemeral','--skip-git-repo-check','--sandbox','read-only','--json',
                            '--output-schema',str(schema),'--output-last-message',str(answer),'--cd',str(task_dir),'-']
    started=time.perf_counter()
    try:
        proc=subprocess.run(command,input=prompt,capture_output=True,text=True,encoding='utf-8',timeout=150)
        elapsed=time.perf_counter()-started
        (task_dir/'events.jsonl').write_text(proc.stdout,encoding='utf-8')
        (task_dir/'stderr.log').write_text(proc.stderr,encoding='utf-8')
        events=[]
        for line in proc.stdout.splitlines():
            try: events.append(json.loads(line))
            except ValueError: pass
        usage=next((e.get('usage') for e in reversed(events) if e.get('type')=='turn.completed'),None)
        if proc.returncode==0 and answer.is_file():
            code=json.loads(answer.read_text(encoding='utf-8'))['code']
            verdict=judge(code,case)
        else:
            verdict=dict(passed=False,result='generation_failed')
        result=dict(task_id=case['task_id'],role=role,model=model,effort=effort,elapsed_seconds=elapsed,
                    usage=usage,exit_code=proc.returncode,verdict=verdict)
    except subprocess.TimeoutExpired as error:
        def decoded(value):return value.decode('utf-8',errors='replace') if isinstance(value,bytes) else value or ''
        (task_dir/'partial-events.jsonl').write_text(decoded(error.stdout),encoding='utf-8')
        (task_dir/'partial-stderr.log').write_text(decoded(error.stderr),encoding='utf-8')
        result=dict(task_id=case['task_id'],role=role,model=model,effort=effort,elapsed_seconds=time.perf_counter()-started,
                    usage=None,exit_code=None,verdict=dict(passed=False,result='generation_timed_out'))
    except (OSError,ValueError,KeyError) as error:
        result=dict(task_id=case['task_id'],role=role,model=model,effort=effort,elapsed_seconds=time.perf_counter()-started,
                    usage=None,exit_code=None,verdict=dict(passed=False,result='harness_error',detail=str(error)))
    result_file.write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


def summarise(results):
    summary={}
    for role,model,effort in MODEL_ROLES:
        rows=[r for r in results if r['role']==role]
        if not rows: continue
        usage=[r['usage'] for r in rows if r.get('usage')]
        summary[role]=dict(model=model,effort=effort,tasks=len(rows),passed=sum(r['verdict']['passed'] for r in rows),
                           generation_timeouts=sum(r['verdict']['result']=='generation_timed_out' for r in rows),
                           code_test_failures=sum(r['verdict']['result'] in ('AssertionError','TypeError','ValueError','NameError') for r in rows),
                           median_seconds=statistics.median(r['elapsed_seconds'] for r in rows),
                           input_tokens=sum(u.get('input_tokens',0) for u in usage),
                           output_tokens=sum(u.get('output_tokens',0) for u in usage),
                           cached_input_tokens=sum(u.get('cached_input_tokens',0) for u in usage),
                           usage_observed=len(usage),usd_cost=None)
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit',type=int,default=1,help='1–8 cases; three hosted model requests per uncached case')
    parser.add_argument('--run-dir',type=Path,default=BASE/'output/outcome-benchmark')
    args=parser.parse_args()
    cases=json.loads((BASE/'benchmarks/humaneval/cases.json').read_text(encoding='utf-8'))[:args.limit]
    if not 1<=args.limit<=8: parser.error('Use1–8 cases')
    args.run_dir=args.run_dir.resolve()
    args.run_dir.mkdir(parents=True,exist_ok=True)
    dataset_sha256=hashlib.sha256((BASE/'benchmarks/humaneval/cases.json').read_bytes()).hexdigest()
    ensure_run_manifest(args.run_dir,dataset_sha256)
    results=[]
    for index,case in enumerate(cases):
        ordered=MODEL_ROLES[index%3:]+MODEL_ROLES[:index%3]
        for role,model,effort in ordered:
            result=generate(case,role,model,effort,args.run_dir)
            results.append(result)
            print(json.dumps(result),flush=True)
            report=dict(scope=f'{len(cases)} pinned public HumanEval cases, one completion per model/task; small historical benchmark, possible memorisation, no statistical superiority claim',
                        requested_cases=len(cases),
                        dataset_sha256=dataset_sha256,
                        summary=summarise(results),results=results,
                        cost_note='Observed token counts only; no verified dollar cost for the signed-in Codex plan. Do not treat tokens as equal-priced across models.')
            (args.run_dir/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


if __name__=='__main__': main()
