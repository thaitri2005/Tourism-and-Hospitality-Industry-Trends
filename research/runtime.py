"""Standard-library runtime support, also used before dependencies are installed."""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time
import traceback
import uuid
from datetime import datetime, timezone

_log = None
_phase = 'starting'

def utcnow():
    return datetime.now(timezone.utc).isoformat()

def atomic_bytes(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)

def atomic_json(path, data):
    atomic_bytes(path, json.dumps(data, indent=2, ensure_ascii=False, default=str).encode('utf-8'))

def fingerprint(*paths, extra=''):
    digest = hashlib.sha256(extra.encode())
    for path in paths:
        digest.update(Path(path).name.encode())
        digest.update(Path(path).read_bytes())
    return digest.hexdigest()

def event(name, level='INFO', **fields):
    record = dict(time=utcnow(), level=level, event=name, phase=_phase, **fields)
    if _log:
        _log.emit(record)
    elif level != 'DEBUG':
        print(json.dumps(record, ensure_ascii=False, default=str), flush=True)

def exception(name, **fields):
    event(name, level='ERROR', traceback=traceback.format_exc(), **fields)

def phase(name):
    global _phase
    _phase = name
    event('phase_started')

class Tee:
    def __init__(self, stream, logfile, lock):
        self.stream, self.logfile, self.lock = stream, logfile, lock
    def write(self, value):
        with self.lock:
            self.logfile.write(value)
            self.logfile.flush()
            self.stream.write(value)
            self.stream.flush()
        return len(value)
    def flush(self):
        self.stream.flush()
    def isatty(self):
        return False
    @property
    def encoding(self):
        return 'utf-8'

class RunLog:
    def __init__(self, directory, verbose=False, capture_console=True):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.run_id = self.directory.name
        self.verbose = verbose
        self.lock = threading.RLock()
        self.events = (self.directory / 'events.jsonl').open('a', encoding='utf-8', buffering=1)
        self.console = (self.directory / 'console.log').open('a', encoding='utf-8', buffering=1) if capture_console else None
        self.original = sys.stdout, sys.stderr
        if capture_console:
            sys.stdout = Tee(sys.stdout, self.console, self.lock)
            sys.stderr = Tee(sys.stderr, self.console, self.lock)
        global _log
        _log = self
    def emit(self, record):
        record['run_id'] = self.run_id
        with self.lock:
            self.events.write(json.dumps(record, ensure_ascii=False, default=str) + '\n')
            self.events.flush()
            if record['level'] != 'DEBUG' or self.verbose:
                detail = {k:v for k,v in record.items() if k not in ('time','level','event','run_id','traceback')}
                print(f"{record['time'][11:19]} {record['level']:5} {record['event']} " + json.dumps(detail, ensure_ascii=False, default=str), flush=True)
    def close(self):
        global _log
        _log = None
        sys.stdout, sys.stderr = self.original
        self.events.close()
        if self.console:
            self.console.close()

class AlreadyRunning(RuntimeError):
    pass

class RunLock:
    """An OS lock: released by the OS even after a crash. Never delete this file."""
    def __init__(self, path):
        self.path = Path(path)
    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.path.open('a+b')
        self.stream.seek(0, 2)
        if self.stream.tell() == 0:
            self.stream.write(b' ')
            self.stream.flush()
        self.stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.stream.close()
            raise AlreadyRunning(f'Another run holds {self.path.name}. Use its terminal; do not delete the lock.') from exc
        self.stream.seek(1)
        self.stream.truncate()
        self.stream.write(json.dumps({'pid':os.getpid(), 'started_at':utcnow()}).encode())
        self.stream.flush()
        return self
    def __exit__(self, *args):
        self.stream.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(self.stream.fileno(), fcntl.LOCK_UN)
        self.stream.close()

class StopRequested(Exception):
    pass

def check_stop(data_dir, source=None):
    markers = [Path(data_dir)/'STOP']
    if source:
        markers.append(Path(data_dir)/('STOP_'+source))
    for marker in markers:
        if marker.exists():
            raise StopRequested(str(marker))

def pause(seconds, data_dir, source=None):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        check_stop(data_dir, source)
        time.sleep(min(.25, max(0, deadline-time.monotonic())))

@contextlib.contextmanager
def heartbeat(seconds=30):
    done = threading.Event()
    def beat():
        while not done.wait(seconds):
            event('heartbeat', message='Still working; Ctrl+C stops safely.')
    worker = threading.Thread(target=beat, daemon=True)
    worker.start()
    try:
        yield
    finally:
        done.set()
        worker.join(timeout=1)
