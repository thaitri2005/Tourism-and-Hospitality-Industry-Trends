import json
import sqlite3
from datetime import datetime, timezone
from .config import DATA, OUTPUT

def now():
    return datetime.now(timezone.utc).isoformat()

def connect():
    DATA.mkdir(exist_ok=True)
    OUTPUT.mkdir(exist_ok=True)
    db = sqlite3.connect(DATA / 'corpus.sqlite', timeout=60)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA journal_mode=WAL')
    db.executescript('''
    CREATE TABLE IF NOT EXISTS urls (
        url TEXT PRIMARY KEY, source TEXT NOT NULL, discovered_via TEXT,
        sitemap_modified TEXT, hint_date TEXT, hint_title TEXT,
        status TEXT DEFAULT 'discovered', error TEXT, discovered_at TEXT,
        fetched_at TEXT
    );
    CREATE TABLE IF NOT EXISTS documents (
        doc_id TEXT PRIMARY KEY, source TEXT, url TEXT UNIQUE, canonical_url TEXT,
        title TEXT, published_at TEXT, modified_at TEXT, date_evidence TEXT,
        date_confidence TEXT, language TEXT, content_type TEXT, body TEXT,
        word_count INTEGER, content_hash TEXT, raw_path TEXT, retrieved_at TEXT,
        quality_flags TEXT, eligible INTEGER, exclusion_reason TEXT,
        publisher TEXT, author TEXT, duplicate_cluster TEXT
    );
    CREATE TABLE IF NOT EXISTS audit (
        source TEXT PRIMARY KEY, checked_at TEXT, payload TEXT
    );
    CREATE TABLE IF NOT EXISTS requests (
        id INTEGER PRIMARY KEY, source TEXT, url TEXT, checked_at TEXT,
        status INTEGER, error TEXT, purpose TEXT
    );
    CREATE TABLE IF NOT EXISTS source_state (
        source TEXT PRIMARY KEY, state TEXT, reason TEXT, until_at TEXT, updated_at TEXT
    );
    CREATE TABLE IF NOT EXISTS fetch_failures (
        source TEXT, url TEXT, category TEXT, status INTEGER, error TEXT,
        retryable INTEGER, next_retry_at TEXT, updated_at TEXT,
        PRIMARY KEY(source,url)
    );
    CREATE TABLE IF NOT EXISTS checkpoints (
        name TEXT PRIMARY KEY, fingerprint TEXT, status TEXT, payload TEXT, updated_at TEXT
    );
    ''')
    # Additive migrations preserve the existing pilot corpus.
    additions = {
        'urls': {'attempts':'INTEGER DEFAULT 0', 'next_retry_at':'TEXT',
                 'error_kind':'TEXT', 'last_run':'TEXT', 'extractor_version':'TEXT'},
        'documents': {'extractor_version':'TEXT'},
        'requests': {'run_id':'TEXT', 'attempt':'INTEGER', 'elapsed_ms':'INTEGER',
                     'bytes':'INTEGER', 'cache_hit':'INTEGER', 'category':'TEXT'},
    }
    for table, columns in additions.items():
        existing = {r[1] for r in db.execute('PRAGMA table_info('+table+')')}
        for name, sql_type in columns.items():
            if name not in existing:
                db.execute(f'ALTER TABLE {table} ADD COLUMN {name} {sql_type}')
    db.execute('CREATE INDEX IF NOT EXISTS urls_queue ON urls(source,status,next_retry_at)')
    db.execute('CREATE INDEX IF NOT EXISTS request_source_history ON requests(source,id)')
    db.commit()
    return db

def checkpoint(db, name, version, status, payload=None):
    db.execute('INSERT OR REPLACE INTO checkpoints VALUES(?,?,?,?,?)',
               (name,version,status,json.dumps(payload or {}),now()))
    db.commit()

def completed(db, name, version):
    row = db.execute('SELECT * FROM checkpoints WHERE name=?',(name,)).fetchone()
    return bool(row and row['fingerprint']==version and row['status']=='complete')

def set_source_state(db, source, state, reason='', until_at=None):
    db.execute('INSERT OR REPLACE INTO source_state VALUES(?,?,?,?,?)',
               (source,state,reason,until_at,now()))
    db.commit()

def record_audit(db, source, payload):
    db.execute('INSERT OR REPLACE INTO audit VALUES (?,?,?)', (source, now(), json.dumps(payload)))
    db.commit()

def add_url(db, source, url, via, modified='', hint_date='', hint_title=''):
    db.execute('''INSERT INTO urls(url,source,discovered_via,sitemap_modified,hint_date,hint_title,discovered_at)
      VALUES(?,?,?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET
      hint_date=CASE WHEN excluded.hint_date<>'' THEN excluded.hint_date ELSE urls.hint_date END,
      hint_title=CASE WHEN excluded.hint_title<>'' THEN excluded.hint_title ELSE urls.hint_title END''',
      (url,source,via,modified,hint_date,hint_title,now()))
