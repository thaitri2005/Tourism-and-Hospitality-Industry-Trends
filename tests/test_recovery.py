"""Offline failure injection: never contact publisher sites during these tests."""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
import pytest
from research import store, http, crawl, runtime, discover, backfill, reextract, run, diagnostics

BASE = 'https://wttc.org'
URL = BASE+'/news/test-article'

def article(number=1):
    return (f'<html lang="en"><meta property="article:published_time" content="2020-01-0{number}">'
            f'<h1>Tourism research article {number}</h1><div class="details-block__lead-paragraph">'
            + (f'The tourism sector is investing in sustainability and climate action for the future {number}. '*30)
            + '</div></html>').encode()

class Response(io.BytesIO):
    def __init__(self,url,data,content_type='text/html'):
        super().__init__(data)
        self.url,self.status,self.headers = url,200,{'Content-Type':content_type}
    def geturl(self):
        return self.url

class FakeNetwork:
    def __init__(self):
        self.calls = []
        self.script = {}
    def open(self,request,timeout):
        url = request.full_url
        self.calls.append(url)
        if url.endswith('/robots.txt'):
            return Response(url,b'User-agent: *\nAllow: /\n','text/plain')
        choices = self.script.get(url)
        if not choices:
            raise AssertionError('Unexpected network request: '+url)
        response = choices.pop(0)
        if isinstance(response,BaseException):
            raise response
        return Response(url,response)

@pytest.fixture
def workspace(tmp_path,monkeypatch):
    data,output = tmp_path/'data',tmp_path/'output'
    data.mkdir();output.mkdir()
    for module in [store,http,crawl,discover,backfill,reextract,run,diagnostics]:
        if hasattr(module,'DATA'):
            monkeypatch.setattr(module,'DATA',data)
        if hasattr(module,'OUTPUT'):
            monkeypatch.setattr(module,'OUTPUT',output)
    monkeypatch.setattr(reextract,'ROOT',tmp_path)
    monkeypatch.setattr(diagnostics,'ROOT',tmp_path)
    monkeypatch.setenv('TOURISM_RUN_ID','test-run-1')
    monkeypatch.setattr(http,'pause',lambda seconds,directory,source=None:runtime.check_stop(directory,source))
    network = FakeNetwork()
    monkeypatch.setattr(http.urllib.request,'build_opener',lambda *args:network)
    db = store.connect()
    db.close()
    return data,output,network

def add_candidate(url=URL):
    db = store.connect()
    store.add_url(db,'wttc',url,'test fixture')
    db.commit();db.close()

def row(url=URL):
    db = store.connect()
    value = dict(db.execute('SELECT * FROM urls WHERE url=?',(url,)).fetchone())
    db.close()
    return value

def http_error(code,headers=None):
    return urllib.error.HTTPError(URL,code,'fixture failure',headers or {},None)

def test_timeout_then_success_records_every_attempt_and_reuses_cache(workspace):
    data,_,network = workspace
    network.script[URL] = [TimeoutError('timeout fixture'),article()]
    db = store.connect()
    fetcher = http.Fetcher('wttc',db,delay=0)
    first,meta = fetcher.fetch(URL)
    second,_ = fetcher.fetch(URL)
    assert first==second==article()
    assert network.calls==[URL,URL]
    attempts = [dict(r) for r in db.execute('SELECT * FROM requests ORDER BY id')]
    assert [r['attempt'] for r in attempts]==[1,2,0]
    assert attempts[0]['category']=='transport'
    assert attempts[1]['bytes']==len(article())
    assert attempts[2]['cache_hit']==1
    assert not db.execute('SELECT * FROM fetch_failures').fetchall()
    db.close()

def test_retry_budget_and_identical_command_after_cooldown(workspace,monkeypatch):
    _,_,network = workspace
    add_candidate()
    network.script[URL] = [TimeoutError('offline') for _ in range(3)] + [article()]
    crawl.run_source('wttc')
    assert row()['status']=='retry_wait'
    assert network.calls.count(URL)==3
    monkeypatch.setenv('TOURISM_RUN_ID','test-run-2')
    crawl.run_source('wttc')
    assert network.calls.count(URL)==3  # Does not retry before the saved deadline.
    db = store.connect()
    db.execute("UPDATE urls SET next_retry_at='2000-01-01' WHERE url=?",(URL,))
    db.execute("UPDATE fetch_failures SET next_retry_at='2000-01-01' WHERE url=?",(URL,))
    db.commit();db.close()
    monkeypatch.setenv('TOURISM_RUN_ID','test-run-3')
    crawl.run_source('wttc')
    assert row()['status']=='extracted'
    assert row()['attempts']==2
    assert network.calls.count(URL)==4

@pytest.mark.parametrize('code',[429,503])
def test_retry_after_survives_new_fetcher_and_never_retries_early(workspace,code):
    _,_,network = workspace
    network.script[URL] = [http_error(code,{'Retry-After':'3600'})]
    db = store.connect()
    with pytest.raises(http.FetchError) as caught:
        http.Fetcher('wttc',db).fetch(URL)
    wait = (datetime.fromisoformat(caught.value.next_retry_at)-datetime.now(timezone.utc)).total_seconds()
    assert 3590<wait<=3600
    with pytest.raises(http.FetchError,match='HTTP'):
        http.Fetcher('wttc',db).fetch(URL)
    assert network.calls==[URL]
    db.close()

def test_access_denial_is_persistent_and_not_an_endless_retry(workspace,monkeypatch):
    _,_,network = workspace
    add_candidate()
    network.script[URL] = [http_error(403)]
    crawl.run_source('wttc')
    assert row()['status']=='permanent_error'
    count = len(network.calls)
    monkeypatch.setenv('TOURISM_RUN_ID','test-run-2')
    result = crawl.run_source('wttc')
    assert result['status']=='source_unavailable'
    assert len(network.calls)==count

def test_dead_url_is_recorded_without_retrying(workspace):
    _,_,network = workspace
    network.script[URL] = [http_error(404)]
    db = store.connect()
    for _ in range(2):
        with pytest.raises(http.FetchError) as caught:
            http.Fetcher('wttc',db).fetch(URL)
        assert caught.value.status==404
        assert not caught.value.retryable
    assert network.calls==[URL]
    db.close()

def test_corrupt_cache_is_repaired(workspace):
    data,_,network = workspace
    network.script[URL] = [article(),article()]
    db = store.connect()
    fetcher = http.Fetcher('wttc',db)
    fetcher.fetch(URL)
    key = hashlib.sha256(URL.encode()).hexdigest()
    (data/'http_cache'/'wttc'/(key+'.gz')).write_bytes(b'corrupt gzip fixture')
    assert fetcher.fetch(URL)[0]==article()
    assert len(network.calls)==2
    db.close()

def test_interruption_after_download_reuses_response_and_does_not_duplicate(workspace,monkeypatch):
    _,_,network = workspace
    add_candidate()
    network.script[URL] = [article()]
    original = crawl.atomic_bytes
    def interrupt(*args):
        raise KeyboardInterrupt()
    monkeypatch.setattr(crawl,'atomic_bytes',interrupt)
    with pytest.raises(KeyboardInterrupt):
        crawl.run_source('wttc')
    assert row()['status']=='discovered'
    count = len(network.calls)
    monkeypatch.setattr(crawl,'atomic_bytes',original)
    monkeypatch.setenv('TOURISM_RUN_ID','test-run-2')
    crawl.run_source('wttc')
    crawl.run_source('wttc')
    assert len(network.calls)==count
    assert row()['status']=='extracted'
    db = store.connect()
    assert db.execute('SELECT COUNT(*) FROM documents').fetchone()[0]==1
    db.close()

def test_hard_kill_claim_recovery_and_extractor_fix_retry(workspace):
    add_candidate()
    add_candidate(URL+'-fixed')
    db = store.connect()
    db.execute("UPDATE urls SET status='in_progress' WHERE url=?",(URL,))
    db.execute("UPDATE urls SET status='extraction_error',extractor_version='old-code' WHERE url=?",(URL+'-fixed',))
    db.commit()
    assert crawl.recover(db)==1
    assert {r[0] for r in db.execute('SELECT status FROM urls')}=={'discovered'}
    db.close()

def test_changed_extractor_reprocesses_raw_once_without_network(workspace,monkeypatch):
    _,_,network = workspace
    add_candidate()
    network.script[URL] = [article()]
    crawl.run_source('wttc')
    db = store.connect()
    db.execute("UPDATE documents SET extractor_version='older'")
    db.commit();db.close()
    count = len(network.calls)
    assert reextract.main()==dict(updated=1,errors=0)
    assert reextract.main()==dict(updated=0,errors=0)
    assert len(network.calls)==count

def test_stop_file_blocks_network(workspace):
    data,_,network = workspace
    (data/'STOP').touch()
    db = store.connect()
    with pytest.raises(runtime.StopRequested):
        http.Fetcher('wttc',db).fetch(URL)
    assert network.calls==[]
    db.close()

def test_robots_rules_apply_to_redirect_targets(workspace):
    db = store.connect()
    fetcher = http.Fetcher('wttc',db)
    fetcher.robot = http.RobotFileParser()
    fetcher.robot.parse(['User-agent: *','Disallow: /private/'])
    handler = http.CheckedRedirect(fetcher)
    with pytest.raises(http.FetchError,match='disallows'):
        handler.redirect_request(urllib.request.Request(URL),None,302,'redirect',{},BASE+'/private/file')
    with pytest.raises(http.FetchError,match='Outside'):
        handler.redirect_request(urllib.request.Request(URL),None,302,'redirect',{},'https://other.example/file')
    db.close()

def test_atomic_write_preserves_existing_file_when_replace_fails(tmp_path,monkeypatch):
    path = tmp_path/'example.json'
    path.write_bytes(b'previous valid snapshot')
    def fail(*args):
        raise PermissionError('replace interrupted')
    monkeypatch.setattr(runtime.os,'replace',fail)
    with pytest.raises(PermissionError):
        runtime.atomic_bytes(path,b'new snapshot')
    assert path.read_bytes()==b'previous valid snapshot'
    assert list(tmp_path.glob('*.tmp'))==[]

def test_os_lock_rejects_other_process_and_releases_after_owner_exit(tmp_path):
    path = tmp_path/'run.lock'
    script = "from research.runtime import RunLock; from pathlib import Path; import sys;\nwith RunLock(Path(sys.argv[1])): print('acquired')"
    with runtime.RunLock(path):
        blocked = subprocess.run([sys.executable,'-c',script,str(path)],capture_output=True,text=True)
        assert blocked.returncode!=0 and 'Another run holds' in blocked.stderr
    resumed = subprocess.run([sys.executable,'-c',script,str(path)],capture_output=True,text=True)
    assert resumed.returncode==0 and 'acquired' in resumed.stdout

def test_legacy_schema_migration_preserves_existing_urls(tmp_path,monkeypatch):
    data = tmp_path/'data';data.mkdir()
    monkeypatch.setattr(store,'DATA',data)
    monkeypatch.setattr(store,'OUTPUT',tmp_path/'output')
    db = sqlite3.connect(data/'corpus.sqlite')
    db.execute('''CREATE TABLE urls(url TEXT PRIMARY KEY,source TEXT NOT NULL,discovered_via TEXT,
        sitemap_modified TEXT,hint_date TEXT,hint_title TEXT,status TEXT DEFAULT 'discovered',
        error TEXT,discovered_at TEXT,fetched_at TEXT)''')
    db.execute("INSERT INTO urls(url,source,status) VALUES(?,?,'extracted')",(URL,'wttc'))
    db.commit();db.close()
    migrated = store.connect()
    kept = migrated.execute('SELECT * FROM urls').fetchone()
    assert kept['url']==URL and kept['status']=='extracted' and kept['attempts']==0
    migrated.close()

def test_diagnostics_excludes_corpus_raw_cache_and_body(workspace):
    data,output,_ = workspace
    secret = 'PRIVATE FULL ARTICLE TEXT FIXTURE'
    db = store.connect()
    db.execute('INSERT INTO documents(doc_id,source,url,body,eligible) VALUES(?,?,?,?,?)',('x','wttc',URL,secret,0))
    db.commit();db.close()
    (data/'raw').mkdir();(data/'raw'/'secret.txt').write_text(secret)
    bundle = diagnostics.make_bundle()
    with zipfile.ZipFile(bundle) as archive:
        assert 'status.json' in archive.namelist()
        assert all('corpus.sqlite' not in name and '/raw/' not in name for name in archive.namelist())
        assert all(secret.encode() not in archive.read(name) for name in archive.namelist())

def test_full_pipeline_second_run_avoids_network_and_analysis(workspace,monkeypatch):
    _,output,network = workspace
    sources = {key:dict(value) for key,value in run.SOURCES.items()}
    for key,value in sources.items():
        if key!='wttc':
            value['access']='publisher_authorization_required'
    for module in [run,discover,crawl,http,diagnostics]:
        monkeypatch.setattr(module,'SOURCES',sources)
    network.script[BASE+'/sitemap.xml'] = [('<urlset>'+''.join(f'<url><loc>{URL}-{i}</loc></url>' for i in range(1,4))+'</urlset>').encode()]
    for route in ['/sitemap_index.xml','/wp-sitemap.xml']:
        network.script[BASE+route] = [http_error(404)]
    for route in ['/news','/blog','/reports-insights']:
        network.script[BASE+route] = [b'<html><main>No further article links.</main></html>']
    for i in range(1,4):
        network.script[URL+f'-{i}'] = [article(i)]
    args = argparse.Namespace(offline=False,limit_per_source=100000)
    first = run.execute(args)
    assert first['exit_code']==0
    assert first['progress']['total_documents']==3
    assert first['analysis_current']
    assert (output/'PRELIMINARY_REPORT.md').is_file()
    count = len(network.calls)
    from research import analyze
    def unexpected():
        raise AssertionError('Unchanged analysis must not run again')
    monkeypatch.setattr(analyze,'main',unexpected)
    monkeypatch.setenv('TOURISM_RUN_ID','test-run-2')
    second = run.execute(args)
    assert second['exit_code']==0
    assert second['results']['analysis']['status']=='checkpoint_reused'
    assert len(network.calls)==count

def test_setup_retries_after_partial_install(tmp_path,monkeypatch):
    import run_research as launcher
    monkeypatch.setattr(launcher,'ROOT',tmp_path)
    (tmp_path/'requirements.txt').write_text('example-dependency==1\n')
    python = tmp_path/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    python.parent.mkdir(parents=True);python.touch()
    calls = []
    results = iter([1,0,0,0])  # First install fails, second install + imports + pip check pass.
    def command(args):
        if args[-1]=='--version':return 0
        calls.append(args)
        return next(results)
    monkeypatch.setattr(launcher,'logged_command',command)
    with pytest.raises(RuntimeError,match='installation failed'):
        launcher.prepare_environment()
    assert not (tmp_path/'.venv'/'research_environment.json').exists()
    assert launcher.prepare_environment()==python
    assert (tmp_path/'.venv'/'research_environment.json').is_file()
    assert sum('install' in call for call in calls)==2

def test_failed_dependency_import_forces_repair_on_same_command(tmp_path,monkeypatch):
    import run_research as launcher
    monkeypatch.setattr(launcher,'ROOT',tmp_path)
    (tmp_path/'requirements.txt').write_text('example-dependency==1\n')
    python = tmp_path/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    python.parent.mkdir(parents=True);python.touch()
    calls=[];results=iter([0,1,0,0,0])
    def command(args):
        if args[-1]=='--version':return 0
        calls.append(args)
        return next(results)
    monkeypatch.setattr(launcher,'logged_command',command)
    with pytest.raises(RuntimeError,match='validation failed'):
        launcher.prepare_environment()
    assert (tmp_path/'.venv'/'research_repair_required').is_file()
    launcher.prepare_environment()
    assert '--force-reinstall' in calls[2]
    assert not (tmp_path/'.venv'/'research_repair_required').exists()

def test_archive_page_checkpoint_survives_interruption(workspace,monkeypatch):
    _,_,network=workspace
    source='untourism';base=backfill.SOURCES[source]['base']
    def page(year,title):
        return (f'<html><article class="node--teaser"><h2><a href="/news/{title}">{title}</a></h2>'
                f'<time datetime="{year}-01-01">Date</time></article></html>').encode()
    network.script[base+'/news?page=0']=[page(2020,'recent')]
    network.script[base+'/news?page=1']=[KeyboardInterrupt(),page(2015,'older')]
    with pytest.raises(KeyboardInterrupt):
        backfill.main()
    db=store.connect()
    saved=json.loads(db.execute("SELECT payload FROM checkpoints WHERE name='english_archive:untourism'").fetchone()[0])
    assert saved['next_page']==1
    db.close()
    result=backfill.main()
    assert result['status']=='complete'
    assert network.calls.count(base+'/news?page=0')==1
    assert network.calls.count(base+'/news?page=1')==2
    count=len(network.calls)
    assert backfill.main()['cached']
    assert len(network.calls)==count

def test_sitemap_frontier_survives_interruption(workspace):
    _,_,network=workspace
    network.script[BASE+'/sitemap.xml']=[b'<sitemapindex><sitemap><loc>https://wttc.org/child.xml</loc></sitemap></sitemapindex>']
    network.script[BASE+'/sitemap_index.xml']=[http_error(404)]
    network.script[BASE+'/wp-sitemap.xml']=[http_error(404)]
    network.script[BASE+'/child.xml']=[KeyboardInterrupt(),('<urlset><url><loc>'+URL+'</loc></url></urlset>').encode()]
    for route in ['/news','/blog','/reports-insights']:
        network.script[BASE+route]=[b'<html><main>Archive</main></html>']
    with pytest.raises(KeyboardInterrupt):
        discover.audit_one('wttc')
    _,result=discover.audit_one('wttc')
    assert result['discovered_urls']==1
    assert network.calls.count(BASE+'/sitemap.xml')==1
    assert network.calls.count(BASE+'/child.xml')==2

def test_failed_analysis_never_overwrites_last_published_report(workspace,monkeypatch):
    _,output,_=workspace
    from research import analyze
    report=output/'PRELIMINARY_REPORT.md'
    report.write_text('previous completed report')
    def fail():
        analyze.OUTPUT.mkdir(parents=True,exist_ok=True)
        (analyze.OUTPUT/'PRELIMINARY_REPORT.md').write_text('incomplete new report')
        raise RuntimeError('simulated model failure')
    monkeypatch.setattr(analyze,'main',fail)
    with pytest.raises(RuntimeError,match='simulated model failure'):
        run.analyze_snapshot()
    assert report.read_text()=='previous completed report'

def test_structured_logs_capture_request_fields_and_tracebacks(tmp_path):
    log=runtime.RunLog(tmp_path/'run')
    try:
        runtime.event('http_attempt',level='DEBUG',url=URL,status=503,attempt=2,elapsed_ms=100,bytes=0)
        try:
            raise ValueError('fixture extraction error')
        except ValueError:
            runtime.exception('extraction_failed',url=URL)
    finally:
        log.close()
    events=[json.loads(line) for line in (tmp_path/'run'/'events.jsonl').read_text('utf-8').splitlines()]
    assert events[0]['status']==503 and events[0]['attempt']==2
    assert all('time' in record and 'run_id' in record for record in events)
    assert 'ValueError: fixture extraction error' in events[1]['traceback']
    assert URL in (tmp_path/'run'/'console.log').read_text('utf-8')

def test_request_spacing_survives_a_new_fetcher(workspace):
    _,_,network=workspace
    network.script[URL]=[article()]
    db=store.connect()
    http.Fetcher('wttc',db).fetch(URL)
    assert .5<http.Fetcher('wttc',db,delay=2).request_delay()<=2
    db.close()

def test_pipeline_stdout_and_early_stderr_are_captured_once(tmp_path):
    import run_research as launcher
    directory=tmp_path/'logs'
    log=runtime.RunLog(directory)
    script=('import sys; from research.runtime import RunLog,event; '
            'print("early startup message",flush=True); '
            'logger=RunLog(sys.argv[1],capture_console=False); '
            'event("child_test_message"); logger.close(); '
            'raise RuntimeError("startup exception fixture")')
    try:
        code=launcher.logged_command([sys.executable,'-u','-c',script,str(directory)],operation='pipeline')
    finally:
        log.close()
    assert code!=0
    console=(directory/'console.log').read_text('utf-8')
    assert console.count('INFO  child_test_message')==1
    assert 'RuntimeError: startup exception fixture' in console
    assert 'early startup message' in console

def test_empty_corpus_is_reported_as_partial_not_an_uncaught_exit(workspace):
    result=run.execute(argparse.Namespace(offline=True,limit_per_source=25))
    assert result['exit_code']==2
    assert result['analysis_current'] is False
    assert any('No documents collected' in item['error'] for item in result['errors'])

def test_setup_repairs_missing_pip(tmp_path,monkeypatch):
    import run_research as launcher
    monkeypatch.setattr(launcher,'ROOT',tmp_path)
    (tmp_path/'requirements.txt').write_text('example-dependency==1\n')
    python=tmp_path/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    python.parent.mkdir(parents=True);python.touch()
    calls=[];returns=iter([1,0,0,0,0])
    def command(args):
        calls.append(args)
        return next(returns)
    monkeypatch.setattr(launcher,'logged_command',command)
    launcher.prepare_environment()
    assert calls[1][-3:]==['-m','ensurepip','--upgrade']

def test_manual_title_correction_invalidates_analysis(workspace):
    _,_,network=workspace
    add_candidate();network.script[URL]=[article()]
    crawl.run_source('wttc')
    db=store.connect()
    before=run.analysis_fingerprint(db)
    db.execute('UPDATE documents SET title=? WHERE url=?',('Corrected research title',URL))
    db.commit()
    assert run.analysis_fingerprint(db)!=before
    db.close()

def test_old_python_gets_a_clear_error_before_setup(monkeypatch,capsys):
    import run_research as launcher
    monkeypatch.setattr(sys,'argv',['run_research.py'])
    monkeypatch.setattr(sys,'version_info',(3,11,0))
    assert launcher.main()==1
    assert 'Python 3.12' in capsys.readouterr().err
