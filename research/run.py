"""Internal pipeline. Start it through python run_research.py."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from .config import ROOT, DATA, OUTPUT, SOURCES
from .store import connect, checkpoint, completed, set_source_state, now, record_audit
from .runtime import (RunLog, RunLock, AlreadyRunning, atomic_bytes, atomic_json, event, exception, phase,
                      fingerprint, check_stop, StopRequested, heartbeat)
from .diagnostics import environment, snapshot

def discover_source(source):
    from .discover import audit_one
    c = SOURCES[source]
    db = connect()
    try:
        if c['access']!='public_research_review':
            payload = dict(name=c['name'],access=c['access'],terms=c['terms'],note=c['note'],
                           discovery_status='held_for_authorization_or_source_verification')
            record_audit(db,source,payload)
            event('source_held',source=source,reason=c['access'])
            return dict(status='held',reason=c['access'])
        state = db.execute('SELECT * FROM source_state WHERE source=?',(source,)).fetchone()
        # These sources received an explicit user-authorized one-time retry.
        # If the current denial is still present, keep the normal durable hold.
        recheck_key='access_recheck:'+source
        recheck_done=completed(db,recheck_key,'user_authorized_once_v1')
        if state and state['state']=='blocked' and c.get('retry_blocked_once') and not recheck_done:
            event('source_access_recheck_authorized',source=source,prior_reason=state['reason'])
            db.execute('DELETE FROM source_state WHERE source=?',(source,));db.commit()
            db.execute('DELETE FROM fetch_failures WHERE source=? AND url=?',
                       (source,c['base']+'/robots.txt'));db.commit()
            state=None
        if state and (state['state']=='blocked' or (state['state']=='cooldown' and (state['until_at'] or '')>now())):
            event('source_deferred',source=source,**{k:state[k] for k in ['state','reason','until_at']})
            return dict(status='deferred',state=dict(state))
        version = fingerprint(ROOT/'research/discover.py',ROOT/'research/config.py')
        key = 'inventory:'+source
        if completed(db,key,version):
            event('inventory_checkpoint_reused',source=source)
            return dict(status='checkpoint_reused')
        _,audit = audit_one(source,max_sitemaps=1000)
        if c.get('retry_blocked_once') and not recheck_done and not audit.get('retryable_errors'):
            checkpoint(db,recheck_key,'user_authorized_once_v1','complete',
                       dict(robots_status=audit.get('robots_status'),errors=audit.get('errors',[])))
        done = audit.get('robots_status') in ('readable','not_found_404') and not audit.get('retryable_errors') and not audit.get('remaining_sitemaps')
        checkpoint(db,key,version,'complete' if done else 'incomplete',audit)
        # "complete" here means discovery attempts finished; errors and archive
        # coverage limitations remain in the source audit, never a census claim.
        return dict(status='processed' if done else 'incomplete',errors=audit.get('errors',[]),
                    remaining_sitemaps=len(audit.get('remaining_sitemaps',[])))
    finally:
        db.close()

def analysis_fingerprint(db):
    digest=hashlib.sha256()
    for name,sql in {
        'documents':'SELECT * FROM documents ORDER BY doc_id',
        'urls':'SELECT * FROM urls ORDER BY url',
        'audit':'SELECT source,payload FROM audit ORDER BY source',
    }.items():
        digest.update(name.encode())
        for row in db.execute(sql):
            # Stream full relevant records, including title/body corrections, so
            # human metadata edits cannot silently reuse an obsolete report.
            digest.update(json.dumps(tuple(row),ensure_ascii=False,separators=(',',':')).encode('utf-8'))
            digest.update(b'\n')
    digest.update(json.dumps(environment()['packages'],sort_keys=True).encode())
    return fingerprint(ROOT/'research/analyze.py',ROOT/'research/codebook.py',ROOT/'research/config.py',
                       extra=digest.hexdigest())

def analyze_snapshot():
    db = connect()
    version = analysis_fingerprint(db)
    marker = OUTPUT/'analysis_state.json'
    previous = {}
    if marker.is_file():
        try:
            previous = json.loads(marker.read_text('utf-8'))
        except ValueError:
            pass
    valid = previous.get('status')=='complete' and previous.get('input_fingerprint')==version
    if valid:
        for relative,digest in previous.get('artifacts',{}).items():
            path = OUTPUT/relative
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
                valid = False
                break
    if valid and previous.get('artifacts') and completed(db,'analysis',version):
        db.close()
        event('analysis_checkpoint_reused',report=str(OUTPUT/'PRELIMINARY_REPORT.md'))
        return dict(status='checkpoint_reused',input_fingerprint=version)
    phase('analysis')
    stage = OUTPUT/'.staging'/os.environ.get('TOURISM_RUN_ID','manual')
    stage.mkdir(parents=True,exist_ok=True)
    checkpoint(db,'analysis',version,'running',dict(staging=str(stage)))
    db.close()
    from . import analyze
    old = analyze.OUTPUT,analyze.TABLES,analyze.FIGURES
    try:
        analyze.OUTPUT,analyze.TABLES,analyze.FIGURES = stage,stage/'tables',stage/'figures'
        analyze.main()
        required = ['PRELIMINARY_REPORT.md','run_summary.json','tables/document_metadata.csv','tables/source_coverage.csv']
        if any(not (stage/name).is_file() for name in required):
            raise RuntimeError('Analysis did not produce the required artifacts')
        artifacts = {path.relative_to(stage).as_posix():hashlib.sha256(path.read_bytes()).hexdigest()
                     for path in stage.rglob('*') if path.is_file()}
        # Publish only after the whole analysis succeeds. The last marker detects
        # a crash during the copy and causes a rebuild on the next identical command.
        atomic_json(marker,dict(status='publishing',input_fingerprint=version))
        for relative in artifacts:
            atomic_bytes(OUTPUT/relative,(stage/relative).read_bytes())
        manifest = dict(status='complete',created_at=now(),input_fingerprint=version,
                        run_id=os.environ.get('TOURISM_RUN_ID'),artifacts=artifacts,
                        validation_status='exploratory; automated audit follows publication; accuracy not independently calibrated')
        atomic_json(marker,manifest)
        db = connect()
        checkpoint(db,'analysis',version,'complete',manifest)
        db.close()
        event('analysis_published',files=len(artifacts),report=str(OUTPUT/'PRELIMINARY_REPORT.md'))
        return dict(status='complete',input_fingerprint=version,files=len(artifacts))
    finally:
        analyze.OUTPUT,analyze.TABLES,analyze.FIGURES = old

def initialize():
    db = connect()
    try:
        integrity = db.execute('PRAGMA quick_check').fetchone()[0]
        if integrity!='ok':
            raise RuntimeError('SQLite integrity check failed: '+integrity)
        from .crawl import recover
        recover(db)
        # Earlier versions counted robots-disallowed URLs toward the consecutive
        # failure threshold. Clear only that source pause when its recorded
        # failures are exclusively per-URL robots decisions.
        for row in db.execute("SELECT * FROM source_state WHERE state='cooldown' AND reason='Five consecutive document failures'").fetchall():
            other_failures=db.execute("SELECT COUNT(*) FROM fetch_failures WHERE source=? AND category<>'robots_disallowed'",
                                      (row['source'],)).fetchone()[0]
            denied=db.execute("SELECT COUNT(*) FROM fetch_failures WHERE source=? AND category='robots_disallowed'",
                              (row['source'],)).fetchone()[0]
            if denied and not other_failures:
                db.execute('DELETE FROM source_state WHERE source=?',(row['source'],))
                event('source_cooldown_recovered',source=row['source'],reason='prior cooldown came only from robots-disallowed URLs',denied_urls=denied)
        db.commit()
        # Preserve the earlier audit's explicit denial. Re-running the new
        # launcher is not a request to retry an already denied source.
        for row in db.execute('SELECT * FROM audit').fetchall():
            payload = json.loads(row['payload'])
            cfg=SOURCES.get(row['source'],{})
            if (payload.get('robots_status')=='unavailable' and any('403' in str(e) for e in payload.get('errors',[]))
                    and not (cfg.get('retry_blocked_once') and not completed(db,'access_recheck:'+row['source'],'user_authorized_once_v1'))):
                existing = db.execute('SELECT 1 FROM source_state WHERE source=?',(row['source'],)).fetchone()
                if not existing:
                    set_source_state(db,row['source'],'blocked','Prior robots audit returned HTTP 403')
        event('database_ready',integrity=integrity)
    finally:
        db.close()

def authorize_blocked_rechecks(sources):
    """Clear saved source holds only for an explicit, user-requested recheck."""
    unknown=sorted(set(sources)-set(SOURCES))
    if unknown:
        raise ValueError('Unknown source(s) for --retry-blocked: '+', '.join(unknown))
    db=connect()
    try:
        for source in sorted(set(sources)):
            state=db.execute("SELECT state,reason FROM source_state WHERE source=?",(source,)).fetchone()
            if not state or state['state']!='blocked':
                event('source_retry_not_blocked',source=source)
                continue
            robots=SOURCES[source]['base']+'/robots.txt'
            db.execute('DELETE FROM source_state WHERE source=?',(source,))
            db.execute('DELETE FROM fetch_failures WHERE source=? AND url=?',(source,robots))
            db.execute('DELETE FROM checkpoints WHERE name IN (?,?)',
                       ('access_recheck:'+source,'inventory:'+source))
            event('source_blocked_recheck_authorized',source=source,prior_reason=state['reason'],
                  request_interval_seconds=3)
        db.commit()
    finally:
        db.close()

def execute(args):
    from .crawl import run_source
    from . import backfill, reextract, content_audit, curate, audit_findings, history
    if getattr(args,'audit_only',False):
        phase('automated_audit')
        audit=content_audit.run_audit(root=OUTPUT.parent)
        if audit['process_complete']:audit_findings.write_findings(OUTPUT.parent)
        return dict(status=audit['status'],exit_code=0 if audit['process_complete'] else 2,
                    results={'audit':audit},analysis_current=audit['process_complete'],study_complete=False,offline=True)
    results = {}
    errors = []
    phase('recovery')
    retry_blocked=getattr(args,'retry_blocked',[])
    if retry_blocked:
        authorize_blocked_rechecks(retry_blocked)
    initialize()
    if not args.offline:
        # Put PATA last: its current public sitemap contains a large article
        # queue, and processing it first would delay the initial attempt on the
        # other requested sources during the same resumable invocation.
        source_order=[s for s in SOURCES if s!='pata']+(['pata'] if 'pata' in SOURCES else [])
        if getattr(args,'sources',None):
            source_order=args.sources
        event('source_schedule',sources=source_order,reason='explicit source order' if getattr(args,'sources',None) else 'PATA queued last due to larger discovered inventory')
        for source in source_order:
            check_stop(DATA)
            phase('discovery:'+source)
            try:
                results['discovery:'+source] = discover_source(source)
            except StopRequested:
                if (DATA/'STOP').exists():
                    raise
                results['discovery:'+source] = dict(status='stopped_by_marker')
                continue
            except Exception as exc:
                exception('discovery_failed',source=source)
                errors.append(dict(phase='discovery',source=source,error=str(exc)))
            if SOURCES[source]['access']!='public_research_review':
                continue
            if source in history.ARCHIVES:
                phase('history:'+source)
                try:
                    results['history:'+source] = history.run_source(source)
                except StopRequested:
                    if (DATA/'STOP').exists():
                        raise
                    results['history:'+source] = dict(status='stopped_by_marker')
                    continue
                except Exception as exc:
                    exception('historical_discovery_failed',source=source)
                    errors.append(dict(phase='history',source=source,error=str(exc)))
            if source=='untourism':
                phase('archive:'+source)
                try:
                    results['archive:'+source] = backfill.main()
                except StopRequested:
                    if (DATA/'STOP').exists():
                        raise
                    results['archive:'+source] = dict(status='stopped_by_marker')
                except Exception as exc:
                    exception('archive_backfill_failed',source=source)
                    errors.append(dict(phase='archive',source=source,error=str(exc)))
            phase('crawl:'+source)
            try:
                results['crawl:'+source] = run_source(source,args.limit_per_source)
            except StopRequested:
                if (DATA/'STOP').exists():
                    raise
                results['crawl:'+source] = dict(status='stopped_by_marker')
            except Exception as exc:
                exception('source_phase_failed',source=source)
                errors.append(dict(phase='crawl',source=source,error=str(exc)))
    phase('reextract')
    reprocessed = reextract.main()
    results['reextract'] = reprocessed
    if reprocessed['errors']:
        errors.append(dict(phase='reextract',error='Some local records still use an older extractor; analysis was not updated'))
    else:
        phase('curation')
        results['curation']=curate.main()
        try:
            results['analysis'] = analyze_snapshot()
        except Exception as exc:
            exception('analysis_failed')
            errors.append(dict(phase='analysis',error=str(exc)))
    if results.get('analysis',{}).get('status') in ('complete','checkpoint_reused'):
        phase('automated_audit')
        try:
            audit=content_audit.run_audit(root=OUTPUT.parent)
            if audit['process_complete']:audit_findings.write_findings(OUTPUT.parent)
            results['audit']=dict(status=audit['status'],counts=audit['counts'],report=str(OUTPUT/'audit/AUDIT_REPORT.md'))
            if not audit['process_complete']:errors.append(dict(phase='automated_audit',error='Automated audit failed; see output/audit/summary.json'))
        except StopRequested:raise
        except Exception as exc:
            exception('automated_audit_failed');errors.append(dict(phase='automated_audit',error=str(exc)))
    progress = snapshot()
    pending = progress.get('pending_urls',0)
    bad_extractions = sum(s['url_states'].get('extraction_error',0) for s in progress['sources'].values())
    phase_pending = any(r.get('status') in ('incomplete','page_limit','stopped_by_marker') for r in results.values())
    held = [s for s,c in SOURCES.items() if c['access']!='public_research_review']
    blocked = [s for s,item in progress['sources'].items() if item.get('runtime_state',{}).get('state')=='blocked']
    cooldowns = [s for s,item in progress['sources'].items() if item.get('runtime_state',{}).get('state')=='cooldown' and (item['runtime_state'].get('until_at') or '')>now()]
    unresolved = bool(errors or pending or bad_extractions or phase_pending or cooldowns)
    return dict(status='partial_needs_followup' if unresolved else 'available_scope_processed',
                exit_code=2 if unresolved else 0,results=results,errors=errors,progress=progress,
                held_sources=held,blocked_sources=blocked,cooldown_sources=cooldowns,
                study_complete=False,offline=args.offline,
                note='Finished work applies only to discovered, accessible material. Automated audit completion does not establish historical completeness or ground-truth accuracy.',
                analysis_current='analysis' in results and results['analysis']['status'] in ('complete','checkpoint_reused'))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit-per-source',type=int,default=100000)
    parser.add_argument('--verbose',action='store_true')
    parser.add_argument('--offline',action='store_true')
    parser.add_argument('--audit-only',action='store_true')
    parser.add_argument('--sources',nargs='+',choices=list(SOURCES),help='Collect only these sources; analysis and audit still cover the entire corpus')
    parser.add_argument('--retry-blocked',nargs='+',default=[],metavar='SOURCE',
                        help='Explicitly recheck named blocked sources once (still honors robots.txt and HTTP denials)')
    args = parser.parse_args()
    if os.environ.get('TOURISM_LAUNCHED')!='1':
        parser.error('Use python run_research.py so setup, the process lock and diagnostics are included.')
    run_dir = Path(os.environ['TOURISM_RUN_DIR'])
    log = RunLog(run_dir,args.verbose,capture_console=False)
    atomic_json(run_dir/'environment.json',environment())
    summary = dict(status='failed',exit_code=1)
    try:
        # This second OS lock survives a killed launcher while this child is alive.
        with RunLock(DATA/'pipeline.lock'), heartbeat():
            summary = execute(args)
    except AlreadyRunning as exc:
        event('pipeline_already_running',level='ERROR',reason=str(exc))
        summary = dict(status='already_running',exit_code=3)
    except (KeyboardInterrupt,StopRequested) as exc:
        event('pipeline_interrupted',level='WARNING',reason=str(exc),message='Rerun the same command to resume.')
        summary = dict(status='interrupted',exit_code=130,analysis_current=False)
    except Exception:
        exception('pipeline_failed')
    finally:
        summary.update(run_id=os.environ.get('TOURISM_RUN_ID'),finished_at=now())
        try:
            summary['progress'] = snapshot()
        except Exception:
            exception('final_status_failed')
        atomic_json(run_dir/'summary.json',summary)
        atomic_json(OUTPUT/'runner_summary.json',summary)
        event('pipeline_finished',status=summary['status'],exit_code=summary['exit_code'])
        log.close()
    return summary['exit_code']

if __name__=='__main__':
    raise SystemExit(main())
