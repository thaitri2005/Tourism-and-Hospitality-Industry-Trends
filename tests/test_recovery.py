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
from research import store, http, crawl, runtime, discover, backfill, reextract, run, diagnostics, curate, history

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
    for module in [store,http,crawl,discover,backfill,reextract,run,diagnostics,curate,history]:
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

def test_configured_403_is_url_local_and_other_public_urls_continue(workspace,monkeypatch):
    _,_,network=workspace
    base='https://www.onecaribbean.org'
    robots_url=base+'/robots.txt'
    page_url=base+'/media/cto-news/example-story/'
    original_open=network.open
    calls=[]
    def return_robots_403(request,timeout):
        calls.append(request.full_url)
        if request.full_url==robots_url:
            raise urllib.error.HTTPError(robots_url,403,'Forbidden',{},None)
        return original_open(request,timeout)
    monkeypatch.setattr(network,'open',return_robots_403)
    network.script[page_url]=[http_error(403)]
    db=store.connect()
    fetcher=http.Fetcher('cto',db,delay=0)
    assert fetcher.robots()==''
    assert fetcher.robot_status=='unavailable_403_allowed_by_rfc9309'
    assert fetcher.robot.can_fetch(http.USER_AGENT,page_url)
    assert db.execute("SELECT 1 FROM source_state WHERE source='cto'").fetchone() is None
    with pytest.raises(http.FetchError) as caught:
        fetcher.fetch(page_url)
    assert caught.value.status==403
    assert caught.value.category=='access_denied_url'
    assert db.execute("SELECT 1 FROM source_state WHERE source='cto'").fetchone() is None
    other_url=base+'/media/cto-news/another-story/'
    network.script[other_url]=[article()]
    assert fetcher.fetch(other_url)[0]==article()
    assert calls==[robots_url,page_url,other_url]
    db.close()

def test_authorized_sources_ignore_disallow_rules_but_keep_rate_limit(workspace,monkeypatch):
    _,_,network=workspace
    base='https://www.onecaribbean.org'
    robots_url=base+'/robots.txt'
    page_url=base+'/media/cto-news/example-story/'
    monkeypatch.setattr(network,'open',lambda request,timeout: Response(
        request.full_url,b'User-agent: *\nDisallow: /media/\nCrawl-delay: 7\n','text/plain'
    ) if request.full_url==robots_url else Response(request.full_url,article()))
    db=store.connect()
    fetcher=http.Fetcher('cto',db,delay=3)
    assert 'Disallow: /media/' in fetcher.robots()
    assert fetcher.robot_status=='readable_authorized_override'
    assert fetcher.delay==7
    assert fetcher.fetch(page_url)[0]==article()
    db.close()

def test_robots_403_fallback_is_not_global(workspace,monkeypatch):
    _,_,network=workspace
    base='https://wttc.org'
    original_open=network.open
    def return_robots_403(request,timeout):
        if request.full_url==base+'/robots.txt':
            raise urllib.error.HTTPError(request.full_url,403,'Forbidden',{},None)
        return original_open(request,timeout)
    monkeypatch.setattr(network,'open',return_robots_403)
    db=store.connect()
    fetcher=http.Fetcher('wttc',db,delay=0)
    with pytest.raises(http.FetchError) as caught:
        fetcher.robots()
    assert caught.value.status==403
    assert fetcher.robot_status=='unavailable'
    assert db.execute("SELECT state FROM source_state WHERE source='wttc'").fetchone()['state']=='blocked'
    db.close()

def test_cto_discovery_continues_from_robots_403_using_configured_routes(workspace,monkeypatch):
    _,_,network=workspace
    base='https://www.onecaribbean.org'
    robots_url=base+'/robots.txt'
    original_open=network.open
    def return_robots_403(request,timeout):
        if request.full_url==robots_url:
            raise urllib.error.HTTPError(robots_url,403,'Forbidden',{},None)
        return original_open(request,timeout)
    monkeypatch.setattr(network,'open',return_robots_403)
    story=base+'/media/cto-news/climate-update/'
    network.script[base+'/sitemap.xml']=[(
        '<urlset><url><loc>'+story+'</loc></url></urlset>'
    ).encode()]
    network.script[base+'/sitemap_index.xml']=[b'<urlset></urlset>']
    network.script[base+'/wp-sitemap.xml']=[b'<urlset></urlset>']
    network.script[base+'/media/cto-news/']=[b'<main>Archive</main>']
    network.script[base+'/statistics/annual-reviews-prospects/']=[b'<main>Archive</main>']
    _,audit=discover.audit_one('cto')
    assert audit['robots_status']=='unavailable_403_allowed_by_rfc9309'
    assert audit['discovery_status']=='sitemaps_and_seed_archives_processed'
    assert audit['discovered_urls']==1
    db=store.connect()
    assert db.execute("SELECT 1 FROM source_state WHERE source='cto'").fetchone() is None
    db.close()

def test_cto_discovery_skips_denied_sitemap_then_processes_remaining_routes(workspace):
    _,_,network=workspace
    base='https://www.onecaribbean.org'
    story=base+'/media/cto-news/climate-update/'
    denied=urllib.error.HTTPError(base+'/sitemap.xml',403,'Forbidden',{},None)
    network.script[base+'/sitemap.xml']=[denied]
    network.script[base+'/sitemap_index.xml']=[b'<urlset><url><loc>'+story.encode()+b'</loc></url></urlset>']
    network.script[base+'/wp-sitemap.xml']=[b'<urlset></urlset>']
    network.script[base+'/media/cto-news/']=[b'<main>Archive</main>']
    network.script[base+'/statistics/annual-reviews-prospects/']=[b'<main>Archive</main>']
    _,audit=discover.audit_one('cto')
    assert audit['discovery_status']=='sitemaps_and_seed_archives_processed_with_url_denials'
    assert [item['url'] for item in audit['denied_urls']]==[base+'/sitemap.xml']
    assert base+'/sitemap_index.xml' in network.calls
    assert base+'/wp-sitemap.xml' in network.calls
    assert base+'/media/cto-news/' in network.calls
    assert base+'/statistics/annual-reviews-prospects/' in network.calls
    assert audit['discovered_urls']==1

def test_cto_crawl_skips_one_403_article_and_continues(workspace):
    data,_,network=workspace
    base='https://www.onecaribbean.org'
    denied=base+'/media/cto-news/denied-story/'
    allowed=base+'/media/cto-news/available-story/'
    db=store.connect()
    store.add_url(db,'cto',denied,'fixture archive')
    store.add_url(db,'cto',allowed,'fixture archive')
    db.commit();db.close()
    network.script[denied]=[urllib.error.HTTPError(denied,403,'Forbidden',{},None)]
    network.script[allowed]=[article()]
    result=crawl.run_source('cto')
    assert result['status']=='queue_processed'
    assert result['attempted']==2
    assert row(denied)['status']=='permanent_error'
    assert row(denied)['error_kind']=='access_denied_url'
    assert row(allowed)['status']=='extracted'
    assert denied in network.calls and allowed in network.calls

def test_initialize_migrates_legacy_cto_travelweekly_403_holds(workspace):
    db=store.connect()
    for source,base in [('cto','https://www.onecaribbean.org'),('travelweekly','https://www.travelweekly.com')]:
        store.set_source_state(db,source,'blocked','HTTP 403: Forbidden')
        db.execute('INSERT OR REPLACE INTO fetch_failures VALUES(?,?,?,?,?,?,?,?)',
                   (source,base+'/sitemap.xml','access_denied',403,'HTTP 403',0,None,store.now()))
        db.execute('INSERT OR REPLACE INTO fetch_failures VALUES(?,?,?,?,?,?,?,?)',
                   (source,base+'/robots.txt','access_denied',403,'HTTP 403',0,None,store.now()))
    store.set_source_state(db,'wttc','blocked','HTTP 403: Forbidden')
    db.commit();db.close()
    run.initialize()
    db=store.connect()
    for source,base in [('cto','https://www.onecaribbean.org'),('travelweekly','https://www.travelweekly.com')]:
        assert db.execute('SELECT 1 FROM source_state WHERE source=?',(source,)).fetchone() is None
        assert db.execute('SELECT category FROM fetch_failures WHERE source=? AND url=?',(source,base+'/sitemap.xml')).fetchone()['category']=='access_denied_url'
        assert db.execute('SELECT category FROM fetch_failures WHERE source=? AND url=?',(source,base+'/robots.txt')).fetchone()['category']=='robots_unavailable'
    assert db.execute("SELECT state FROM source_state WHERE source='wttc'").fetchone()['state']=='blocked'
    db.close()

def test_explicit_blocked_recheck_clears_only_named_source_hold(workspace):
    db=store.connect()
    store.set_source_state(db,'wttc','blocked','HTTP 403: Forbidden')
    store.checkpoint(db,'access_recheck:wttc','user_authorized_once_v1','complete',{})
    store.checkpoint(db,'inventory:wttc','old-inventory','complete',{})
    store.set_source_state(db,'etc','blocked','HTTP 403: Forbidden')
    db.execute('INSERT INTO requests(source,url,status) VALUES (?,?,?)',('wttc',BASE+'/robots.txt',403))
    db.commit();db.close()
    run.authorize_blocked_rechecks(['wttc'])
    db=store.connect()
    assert db.execute("SELECT 1 FROM source_state WHERE source='wttc'").fetchone() is None
    assert db.execute("SELECT 1 FROM checkpoints WHERE name='access_recheck:wttc'").fetchone() is None
    assert db.execute("SELECT 1 FROM checkpoints WHERE name='inventory:wttc'").fetchone() is None
    assert db.execute("SELECT state FROM source_state WHERE source='etc'").fetchone()['state']=='blocked'
    assert db.execute("SELECT COUNT(*) FROM requests WHERE source='wttc'").fetchone()[0]==1
    db.close()

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
    (output/'audit').mkdir()
    (output/'audit/theme_evidence.csv').write_text(secret)
    (output/'audit/entity_contexts.csv').write_text(secret)
    (output/'audit/FINDINGS.md').write_text('Aggregated findings without article excerpts.')
    bundle = diagnostics.make_bundle()
    with zipfile.ZipFile(bundle) as archive:
        assert 'status.json' in archive.namelist()
        assert 'output/audit/FINDINGS.md' in archive.namelist()
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
    for i,route in enumerate(['/news','/blog'],1):
        network.script[BASE+route] = [(f'<main><a href="{URL}-{i}">Story</a>'
             '<input x-ref="searchParams" value=\'{"page":1}\'></main>').encode()]
    for i in range(1,4):
        network.script[URL+f'-{i}'] = [article(i)]
    args = argparse.Namespace(offline=False,limit_per_source=100000)
    first = run.execute(args)
    assert first['exit_code']==0
    assert first['progress']['total_documents']==3
    assert first['analysis_current']
    assert first['results']['audit']['counts']['documents_reviewed']==3
    assert (output/'audit/FINDINGS.md').is_file()
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
    assert second['results']['audit']['counts']['cached_records']==3
    assert len(network.calls)==count
    # Interrupt a fresh audit after one committed record, then use the same
    # audit-only operation to resume without any publisher requests.
    from research import content_audit
    cache=sqlite3.connect(output.parent/'data/content_audit_cache.sqlite')
    cache.execute('DELETE FROM reviews');cache.commit();cache.close()
    calls=[]
    def stop_after_first(*args):
        calls.append(1)
        if len(calls)==2:raise runtime.StopRequested('injected audit interruption')
    audit_args=argparse.Namespace(audit_only=True)
    with monkeypatch.context() as patch:
        patch.setattr(content_audit,'check_stop',stop_after_first)
        with pytest.raises(runtime.StopRequested):run.execute(audit_args)
    resumed=run.execute(audit_args)
    assert resumed['exit_code']==0
    assert resumed['results']['audit']['counts']['cached_records']==1
    assert resumed['results']['audit']['process_complete']
    assert len(network.calls)==count
    manifest=json.loads((output/'audit/audit_state.json').read_text())
    assert manifest['status']=='complete'
    assert manifest['artifacts']['FINDINGS.md']==hashlib.sha256((output/'audit/FINDINGS.md').read_bytes()).hexdigest()

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

def test_new_public_archive_walk_resumes_from_the_last_saved_page(workspace):
    _,_,network=workspace
    base='https://www.onecaribbean.org'
    first=base+'/media/cto-news/'
    second=base+'/media/cto-news/page/2/'
    network.script[first]=[
        b'<main><a href="/media/cto-news/story-one/">Story one</a>'
        b'<a rel="next" href="/media/cto-news/page/2/">Next</a></main>'
    ]
    network.script[second]=[
        KeyboardInterrupt(),
        b'<main><a href="/media/cto-news/story-two/">Story two</a></main>',
    ]
    with pytest.raises(KeyboardInterrupt):
        history.run_source('cto')
    result=history.run_source('cto')
    assert result['status']=='complete'
    assert result['pages']==2
    assert network.calls.count(first)==1
    assert network.calls.count(second)==2
    db=store.connect()
    urls={r['url'] for r in db.execute('SELECT url FROM urls WHERE source=?',('cto',))}
    db.close()
    assert base+'/media/cto-news/story-one/' in urls
    assert base+'/media/cto-news/story-two/' in urls

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


def test_history_page_limit_resumes_cursor_and_completed_walk_uses_no_network(workspace,monkeypatch):
    _,_,network=workspace
    monkeypatch.setattr(history,'ARCHIVES',{'wttc':['/news']})
    network.script[BASE+'/news']=[(f'<main><a href="{URL}-1">First</a>'
        '<input x-ref="searchParams" value=\'{"page":1}\'>'
        '<button class="listing-pagination__button--next" x-on:click="changePage(2)">Next</button></main>').encode()]
    network.script[BASE+'/component/search/index']=[(f'<main><a href="{URL}-2">Second</a>'
        '<button class="circled-selection--active">2</button></main>').encode()]
    first=history.run_source('wttc',max_pages=1)
    assert first['status']=='page_limit'
    assert first['pending']==[BASE+'/news?page=2']
    second=history.run_source('wttc',max_pages=1)
    assert second['status']=='complete' and second['new_urls']==2
    before=list(network.calls)
    assert history.run_source('wttc')['status']=='complete'
    assert network.calls==before
    db=store.connect()
    assert db.execute("SELECT count(*) FROM urls").fetchone()[0]==2
    assert db.execute("SELECT discovered_via FROM urls WHERE url=?",(URL+'-2',)).fetchone()[0]==BASE+'/news?page=2'
    db.close()


def test_readonly_search_post_caches_distinct_pages_separately(workspace):
    _,_,network=workspace
    url=BASE+'/component/search/index'
    network.script[url]=[b'page two',b'page three']
    db=store.connect();f=http.Fetcher('wttc',db)
    assert f.fetch(url,json_payload={'page':2})[0]==b'page two'
    assert f.fetch(url,json_payload={'page':3})[0]==b'page three'
    assert f.fetch(url,json_payload={'page':2})[0]==b'page two'
    assert network.calls==[url,url]
    requests=db.execute('SELECT url,cache_hit FROM requests ORDER BY id').fetchall()
    assert requests[0]['url']!=requests[1]['url']
    assert requests[0]['url']==requests[2]['url'] and requests[2]['cache_hit']==1
    with pytest.raises(ValueError):f.fetch(BASE+'/admin',json_payload={'page':2})
    db.close()
