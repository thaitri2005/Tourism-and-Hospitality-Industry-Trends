"""Shareable operational diagnostics. Does not export bodies or raw downloads."""
import importlib.metadata
import json
import platform
import sqlite3
import sys
import zipfile
from pathlib import Path
from .config import ROOT, DATA, OUTPUT, SOURCES, START, END
from .runtime import atomic_bytes, atomic_json, utcnow

PACKAGES = ['beautifulsoup4','lxml','pandas','numpy','scipy','scikit-learn','matplotlib','pypdf','python-dateutil','textblob']

def environment():
    versions = {}
    for name in PACKAGES:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = 'not installed in this interpreter'
    return dict(python=sys.version,executable=sys.executable,platform=platform.platform(),packages=versions)

def snapshot():
    result = dict(created_at=utcnow(),window_start=START,window_end=END,sources={},database_exists=False)
    for source, config in SOURCES.items():
        result['sources'][source] = dict(access=config['access'],url_states={},documents=0,eligible=0)
    path = DATA/'corpus.sqlite'
    if not path.is_file():
        return result
    result['database_exists'] = True
    db = sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=15)
    db.row_factory = sqlite3.Row
    try:
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'urls' in tables:
            for row in db.execute('SELECT source,status,COUNT(*) AS n FROM urls GROUP BY source,status'):
                result['sources'].setdefault(row['source'],{})['url_states'][row['status']] = row['n']
        if 'documents' in tables:
            for row in db.execute('SELECT source,COUNT(*) AS n,SUM(eligible) AS eligible FROM documents GROUP BY source'):
                result['sources'][row['source']].update(documents=row['n'],eligible=row['eligible'])
        if 'source_state' in tables:
            for row in db.execute('SELECT * FROM source_state'):
                result['sources'][row['source']]['runtime_state'] = dict(row)
        if 'checkpoints' in tables:
            result['checkpoints'] = [dict(r) for r in db.execute('SELECT name,fingerprint,status,updated_at FROM checkpoints')]
        if 'fetch_failures' in tables:
            result['next_retry_at'] = db.execute('SELECT MIN(next_retry_at) FROM fetch_failures WHERE retryable=1').fetchone()[0]
        result['total_documents'] = sum(s['documents'] for s in result['sources'].values())
        result['pending_urls'] = sum(sum(n for state,n in s['url_states'].items() if state in ('discovered','retry_wait','in_progress')) for s in result['sources'].values())
        return result
    finally:
        db.close()

def failures():
    path = DATA/'corpus.sqlite'
    if not path.is_file():
        return {}
    db = sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=15)
    db.row_factory = sqlite3.Row
    try:
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        result = {}
        if 'urls' in tables:
            available = {r[1] for r in db.execute('PRAGMA table_info(urls)')}
            columns = [c for c in ['source','url','status','error','error_kind','attempts','next_retry_at','last_run','fetched_at'] if c in available]
            result['url_failures'] = [dict(r) for r in db.execute('SELECT '+','.join(columns)+" FROM urls WHERE status IN ('retry_wait','permanent_error','extraction_error','fetch_or_extract_error','in_progress') ORDER BY source,url")]
        if 'fetch_failures' in tables:
            result['fetch_failures'] = [dict(r) for r in db.execute('SELECT * FROM fetch_failures ORDER BY source,url')]
        if 'requests' in tables:
            result['recent_request_errors'] = [dict(r) for r in db.execute("SELECT * FROM requests WHERE COALESCE(error,'')<>'' ORDER BY id DESC LIMIT 100")]
        return result
    finally:
        db.close()

def make_bundle(run_dir=None, summary=None):
    OUTPUT.mkdir(parents=True,exist_ok=True)
    directory = OUTPUT/'diagnostics'
    directory.mkdir(exist_ok=True)
    run_id = Path(run_dir).name if run_dir else 'manual'
    destination = directory/(run_id+'.zip')
    temporary = destination.with_suffix('.zip.tmp')
    manifest = dict(created_at=utcnow(),omitted=['corpus.sqlite','raw documents','HTTP cache','environment variables','credentials'],truncated_files=[])
    recent=sorted((ROOT/'logs'/'runs').glob('*'),key=lambda p:p.name,reverse=True)
    last_dir=Path(run_dir) if run_dir else (recent[0] if recent else None)
    actual_environment=environment()
    if last_dir and (last_dir/'environment.json').is_file():
        actual_environment=json.loads((last_dir/'environment.json').read_text('utf-8'))
    if summary is None and last_dir and (last_dir/'summary.json').is_file():
        summary=json.loads((last_dir/'summary.json').read_text('utf-8'))
    try:
        with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as archive:
            for name,value in [('status.json',snapshot()),('failures.json',failures()),('environment.json',actual_environment),('summary.json',summary or {})]:
                archive.writestr(name,json.dumps(value,indent=2,ensure_ascii=False,default=str))
            source_files = list((ROOT/'research').glob('*.py')) + list((ROOT/'docs').glob('*.md')) + [ROOT/'run_research.py',ROOT/'requirements.txt',ROOT/'requirements.in',ROOT/'README.md']
            for path in source_files:
                if path.is_file():
                    archive.write(path,'code/'+path.relative_to(ROOT).as_posix())
            directories = sorted((ROOT/'logs'/'runs').glob('*'),key=lambda p:p.name,reverse=True)[:3]
            for logdir in directories:
                for name in ['events.jsonl','console.log','summary.json','environment.json']:
                    path = logdir/name
                    if not path.is_file():
                        continue
                    if path.stat().st_size>20_000_000:
                        with path.open('rb') as stream:
                            stream.seek(-20_000_000,2)
                            stream.readline()
                            tail = stream.read()
                        archive.writestr('logs/'+logdir.name+'/'+name+'.tail',tail)
                        manifest['truncated_files'].append(str(path.relative_to(ROOT)))
                    else:
                        archive.write(path,'logs/'+logdir.name+'/'+name)
            for name in ['runner_summary.json','analysis_state.json','run_summary.json','source_audit.json','QUALITY_CHECKS.json']:
                path = OUTPUT/name
                if path.is_file():
                    archive.write(path,'output/'+name)
            archive.writestr('bundle_manifest.json',json.dumps(manifest,indent=2))
        temporary.replace(destination)
        atomic_bytes(directory/'latest.zip',destination.read_bytes())
        return directory/'latest.zip'
    finally:
        temporary.unlink(missing_ok=True)

def print_status():
    state = snapshot()
    print('Source          Saved   Eligible   URL states')
    for source,item in state['sources'].items():
        counts = ', '.join(f'{k}={v}' for k,v in item['url_states'].items()) or item['access']
        print(f"{source:15} {item['documents']:6} {item['eligible']:10}   {counts}")
        if item.get('runtime_state'):
            print('  '+json.dumps(item['runtime_state'],ensure_ascii=False))
    print(f"Saved documents: {state.get('total_documents',0)}; pending candidate URLs: {state.get('pending_urls',0)}")
    if state.get('next_retry_at'):
        print('Earliest recorded retry deadline (UTC): '+state['next_retry_at']+'; past deadlines are eligible now.')
    print('Latest runner summary: '+str(OUTPUT/'runner_summary.json'))
    print('Diagnostics: '+str(OUTPUT/'diagnostics'/'latest.zip'))
