"""One-command setup, recovery, collection, analysis and diagnostics."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
import venv
from datetime import datetime, timezone
from research.config import ROOT, DATA, OUTPUT
from research.runtime import RunLock, AlreadyRunning, RunLog, atomic_json, atomic_bytes, event, exception, fingerprint, heartbeat
from research.diagnostics import environment, make_bundle, print_status

def logged_command(command, operation='setup'):
    event('subprocess_started',command=command,operation=operation)
    process = subprocess.Popen(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                               text=True,encoding='utf-8',errors='replace')
    try:
        for line in process.stdout:
            print(line,end='',flush=True)
        code=process.wait()
        event('subprocess_finished',operation=operation,exit_code=code)
        return code
    except KeyboardInterrupt:
        # Ctrl+C also reaches the console child on Windows. Reap it before
        # releasing the workspace lock, even if it needs explicit termination.
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=10)
        raise
    finally:
        process.stdout.close()

def prepare_environment():
    folder = ROOT/'.venv'
    python = folder/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    requirements = ROOT/'requirements.txt'
    version = fingerprint(requirements,extra=str(sys.version_info[:2]))
    marker = folder/'research_environment.json'
    repair_marker = folder/'research_repair_required'
    if not python.is_file():
        event('environment_creating',path=str(folder))
        venv.EnvBuilder(with_pip=True).create(folder)
    if logged_command([str(python),'-m','pip','--version'])!=0:
        if logged_command([str(python),'-m','ensurepip','--upgrade'])!=0:
            raise RuntimeError('Could not repair pip in .venv. See console.log; global Python was not modified.')
    recorded = {}
    if marker.is_file():
        try:
            recorded = json.loads(marker.read_text('utf-8'))
        except (ValueError,OSError):
            pass
    validate = [str(python),'-c','import bs4,lxml,pandas,numpy,scipy,sklearn,matplotlib,pypdf,dateutil,textblob; print("Dependency imports OK")']
    install = recorded.get('fingerprint')!=version
    repair = repair_marker.exists()
    if not install and not repair:
        repair = logged_command(validate)!=0 or logged_command([str(python),'-m','pip','check'])!=0
    if install or repair:
        command = [str(python),'-m','pip','install','--disable-pip-version-check','--retries','3','--timeout','30','-r',str(requirements)]
        if repair:
            command.append('--force-reinstall')
        if logged_command(command)!=0:
            raise RuntimeError('Dependency installation failed. Rerun the same command; setup is resumable.')
        if logged_command(validate)!=0 or logged_command([str(python),'-m','pip','check'])!=0:
            atomic_bytes(repair_marker,b'Dependency validation failed; force reinstall on the next invocation.\n')
            raise RuntimeError('Dependency validation failed; see setup output in console.log.')
        atomic_json(marker,dict(fingerprint=version,python=str(python)))
        repair_marker.unlink(missing_ok=True)
    return python

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--status',action='store_true',help='Read local progress without installing packages or making network requests')
    parser.add_argument('--diagnostics',action='store_true',help='Rebuild a shareable diagnostics zip without network requests')
    parser.add_argument('--verbose',action='store_true',help='Also print per-request details; JSONL always includes them')
    parser.add_argument('--limit-per-source',type=int,default=100000,help='Bound article attempts per source for this invocation')
    parser.add_argument('--offline',action='store_true',help='Re-extract/analyze existing local data only; setup may still install dependencies')
    parser.add_argument('--retry-blocked',nargs='+',default=[],metavar='SOURCE',
                        help='Explicitly recheck named blocked sources once; access denials stay enforced')
    parser.add_argument('--setup-only',action='store_true',help='Prepare and validate .venv, then stop without crawling or changing the corpus')
    parser.add_argument('--audit-only',action='store_true',help='Run the complete automated audit of the current analysis without crawling')
    from research.config import SOURCES
    parser.add_argument('--sources',nargs='+',choices=list(SOURCES),help='Collect only these sources; analysis and audit still cover the entire corpus')
    args = parser.parse_args()
    if args.sources and (args.offline or args.audit_only or args.setup_only or args.status or args.diagnostics):
        parser.error('--sources requires a collection run')
    if args.retry_blocked and (args.offline or args.audit_only or args.setup_only or args.status or args.diagnostics):
        parser.error('--retry-blocked requires a normal collection run')
    if args.audit_only and (args.offline or args.setup_only or args.status or args.diagnostics):
        parser.error('--audit-only cannot be combined with another operation')
    if args.status:
        print_status()
        return 0
    if args.diagnostics:
        print(make_bundle())
        return 0
    if args.limit_per_source<1:
        parser.error('--limit-per-source must be positive')
    if sys.version_info<(3,12):
        print('Python 3.12 or newer is required by the pinned dependencies; Python 3.12 is tested. Try: py -3.12 run_research.py',file=sys.stderr)
        return 1
    log = None
    try:
        with RunLock(DATA/'runner.lock'):
            with RunLock(DATA/'pipeline.lock'):
                pass  # Detect a still-running child of a killed prior launcher.
            run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
            run_dir = ROOT/'logs'/'runs'/run_id
            os.environ['TOURISM_RUN_ID'] = run_id
            os.environ['TOURISM_RUN_DIR'] = str(run_dir)
            os.environ['TOURISM_LAUNCHED'] = '1'
            os.environ['PYTHONUTF8'] = '1'
            os.environ['MPLCONFIGDIR'] = str(ROOT/'tmp'/'matplotlib')
            os.environ['PIP_CACHE_DIR'] = str(ROOT/'tmp'/'pip-cache')
            log = RunLog(run_dir,args.verbose)
            atomic_json(ROOT/'logs'/'latest.json',dict(run_id=run_id,directory=str(run_dir)))
            atomic_json(run_dir/'bootstrap_environment.json',environment())
            code = 1
            try:
                event('launcher_started',run_directory=str(run_dir),command='python run_research.py')
                with heartbeat():
                    python = prepare_environment()
                if args.setup_only:
                    # Record the target interpreter, not the launcher interpreter.
                    code=logged_command([str(python),'-c',
                        'from pathlib import Path; from research.runtime import atomic_json; from research.diagnostics import environment; import os; atomic_json(Path(os.environ["TOURISM_RUN_DIR"])/"environment.json",environment())'])
                    if code!=0:raise RuntimeError('Environment validation metadata could not be recorded')
                    atomic_json(run_dir/'summary.json',dict(run_id=run_id,status='setup_complete',exit_code=0,
                        operation='setup_only',analysis_current=False,study_complete=False))
                else:
                    command = [str(python),'-u','-m','research.run','--limit-per-source',str(args.limit_per_source)]
                    if args.sources:
                        command.extend(['--sources',*args.sources])
                    if args.verbose:
                        command.append('--verbose')
                    if args.offline:
                        command.append('--offline')
                    if args.audit_only:
                        command.append('--audit-only')
                    if args.retry_blocked:
                        command.extend(['--retry-blocked',*args.retry_blocked])
                    # Parent captures output from process start, including import
                    # errors before the child has initialized its structured logger.
                    code = logged_command(command,operation='pipeline')
            except KeyboardInterrupt:
                code = 130
                event('setup_interrupted',level='WARNING')
            except Exception:
                exception('launcher_failed')
            finally:
                summary_path = run_dir/'summary.json'
                summary = json.loads(summary_path.read_text('utf-8')) if summary_path.is_file() else dict(run_id=run_id,status='interrupted' if code==130 else 'setup_or_child_failed',exit_code=code)
                summary['launcher_exit_code'] = code
                atomic_json(summary_path,summary)
                atomic_json(OUTPUT/'runner_summary.json',summary)
                event('launcher_finished',exit_code=code,summary=str(OUTPUT/'runner_summary.json'))
                try:
                    bundle = make_bundle(run_dir,summary)
                    print('\nSend back this file: '+str(bundle),flush=True)
                except Exception:
                    exception('diagnostics_failed')
                    print('Send the current logs/runs folder if the diagnostics zip could not be created.',flush=True)
                print('Resume with: python run_research.py',flush=True)
            return code
    except AlreadyRunning as exc:
        print(str(exc),file=sys.stderr)
        return 3
    finally:
        if log:
            log.close()

if __name__=='__main__':
    raise SystemExit(main())
