"""Disposable production-mode backend + production SPA with a history fallback.

Requires PHASE14_POSTGRES_URL pointing to a dedicated loopback phase14 database.
Never opens the development DB. Invoked by Playwright; Ctrl+C cleans up its schema.
"""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from uuid import uuid4

import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

FRONTEND = Path(__file__).resolve().parents[1]
BACKEND = FRONTEND.parent / "backend"
url = make_url(os.environ["PHASE14_POSTGRES_URL"])
if url.host not in {"localhost", "127.0.0.1"} or not url.database.startswith("phase14"):
    raise SystemExit("Use a dedicated loopback phase14 test database.")
url = url.set(drivername="postgresql+psycopg")
admin = create_engine(url)
schema = "mp_e2e_" + uuid4().hex
with admin.begin() as db:
    # Windows stops the web server without running `finally`; purge schemas left by earlier runs.
    stale = db.execute(text("SELECT schema_name FROM information_schema.schemata WHERE schema_name LIKE 'mp\\_e2e\\_%'")).scalars().all()
    for name in stale:
        db.execute(text(f'DROP SCHEMA "{name}" CASCADE'))
    db.execute(text(f'CREATE SCHEMA "{schema}"'))
scoped_url = url.update_query_dict({"options": f"-csearch_path={schema}"}).render_as_string(hide_password=False)
process = None
server = None
log = None
scratch = tempfile.TemporaryDirectory(prefix="marketpulse_e2e_")
variables = dict(os.environ, DATABASE_URL=scoped_url, ENVIRONMENT="production", STORAGE_BACKEND="database",
                 JWT_SECRET_KEY="phase14-isolated-test-signing-key-never-deploy", DEBUG="false", SQL_ECHO="false",
                 DATA_DIR=scratch.name, MODEL_ARTIFACT_DIR=str(Path(scratch.name)/"models"),
                 HOST="127.0.0.1", PORT="8184", API_PREFIX="", CORS_ORIGINS="http://127.0.0.1:5184,https://frontend.marketpulse.test",
                 FLIPKART_AFFILIATE_ID="", FLIPKART_AFFILIATE_TOKEN="", FLIPKART_DATA_USE_APPROVED="false")
for category in ("LOGIN","REGISTER","PREDICT","COLLECT","BUILD","IMPORT","DEMO","TRAIN"):
    variables["RATE_LIMIT_" + category] = "10000"  # functional E2E; unit tests verify strict limits

def cleanup(*_):
    if process and process.poll() is None:
        process.terminate()
        process.wait(timeout=20)
    if log:
        log.close()
    with admin.begin() as db:
        db.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
    admin.dispose()
    scratch.cleanup()

try:
    log = (FRONTEND/".e2e-backend.log").open("w",encoding="utf-8")
    process = subprocess.Popen([sys.executable,"-B","-m","app.start"],cwd=BACKEND,env=variables,stdout=log,stderr=subprocess.STDOUT)
    with httpx.Client(base_url="http://127.0.0.1:8184",timeout=180) as client:
        deadline = time.monotonic()+180
        while True:
            if process.poll() is not None:
                raise RuntimeError("Test backend exited; inspect .e2e-backend.log")
            try:
                if client.get("/ready",timeout=2).status_code == 200:break
            except httpx.TransportError:pass
            if time.monotonic()>deadline:raise RuntimeError("Test backend startup timeout")
            time.sleep(.25)
        seed = """
from app.database import SessionLocal
from app.models import User
from app.auth.security import hash_password
with SessionLocal() as db:
    hashed=hash_password('marketpulse1')
    for role in ['viewer','analyst','operator','administrator']:
        db.add(User(email=role+'@example.com',hashed_password=hashed,role=role,full_name=role.title()+' Test'))
    db.commit()
"""
        subprocess.run([sys.executable,"-B","-c",seed],cwd=BACKEND,env=variables,check=True)
        def ok(response):
            response.raise_for_status()
            return response.json()
        token=ok(client.post('/auth/login',json={'email':'operator@example.com','password':'marketpulse1'}))['access_token']
        headers={'Authorization':'Bearer '+token}
        ok(client.post('/data/demo/load',headers=headers))
        data=ok(client.post('/ml/dataset/build',headers=headers,json={'source_types':['demo']}))
        ok(client.post('/ml/train',headers=headers,json={'source_types':['demo'],'models':['random_forest'],'dataset_id':data['dataset_id']}))
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(FRONTEND/'.e2e-dist'),**kwargs)
        def do_GET(self):
            if not Path(self.translate_path(self.path)).is_file():self.path='/index.html'
            super().do_GET()
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',5184),Handler)
    signal.signal(signal.SIGINT,lambda *_:sys.exit(0))
    signal.signal(signal.SIGTERM,lambda *_:sys.exit(0))
    print('Isolated Phase 14 SPA ready',flush=True)
    server.serve_forever()
finally:
    if server:server.server_close()
    cleanup()
