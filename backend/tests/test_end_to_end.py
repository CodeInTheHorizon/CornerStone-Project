"""Run the real API journey in a fresh subprocess and temporary storage."""
import os
from pathlib import Path
import subprocess
import sys


def test_fresh_install_api_journey(tmp_path):
    env = os.environ.copy()
    env.update(DATABASE_URL=f"sqlite:///{(tmp_path/'fresh.db').as_posix()}", DATA_DIR=str(tmp_path/'data'), MODEL_ARTIFACT_DIR=str(tmp_path/'models'), DEBUG='release', ENVIRONMENT='development', JWT_SECRET_KEY='isolated-flow-secret-never-used-in-development')
    script = r'''
import json
from fastapi.testclient import TestClient
from app.main import app
from app.database import engine

def ok(response, status=200):
    assert response.status_code == status, (response.status_code, response.text)
    return response.json()

with TestClient(app) as client:
    assert ok(client.get('/health'))['database']=='connected'
    credentials={'email':'flow@example.com','password':'marketpulse1','full_name':'Flow Test'}
    registration=ok(client.post('/auth/register',json=credentials),201)
    login=ok(client.post('/auth/login',json={k:credentials[k] for k in ('email','password')}))
    headers={'Authorization':'Bearer '+login['access_token']}
    ok(client.get('/auth/me',headers=headers))
    assert ok(client.get('/analytics/summary',headers=headers))['stored_records']==0
    ok(client.get('/data/status',headers=headers))
    assert ok(client.post('/data/demo/load',headers=headers))['stored']==480
    uploaded=[{'platform':'amazon','product_name':'Imported accessory','category':'chargers','price':250,'collection_timestamp':'2026-09-01T09:00:00Z','source_type':'live'}]
    imported=ok(client.post('/data/import',headers=headers,files={'file':('fixture.json',json.dumps(uploaded),'application/json')}))
    assert imported['source_type']=='imported'
    status=ok(client.get('/data/status',headers=headers))
    assert status['records_by_source_type']=={'demo':480,'imported':1}
    dataset=ok(client.post('/ml/dataset/build',headers=headers,json={'source_types':['demo']}))
    assert dataset['rows']==480 and dataset['source_types']==['demo']
    assert 'DEMO' in dataset['notice']
    preview=ok(client.get('/ml/dataset/preview',headers=headers,params={'dataset_id':dataset['dataset_id'],'limit':5}))
    assert len(preview['rows'])==5 and all(row['source_type']=='demo' for row in preview['rows'])
    trained=ok(client.post('/ml/train',headers=headers,json={'dataset_id':dataset['dataset_id'],'models':['random_forest']}))
    assert trained['dataset_source_types']==['demo'] and trained['model_version']=='v1'
    assert trained['majority_baseline'] is not None
    metrics=ok(client.get('/ml/metrics',headers=headers))
    assert metrics['metrics']['accuracy']==trained['metrics']['accuracy']
    options=ok(client.get('/ml/prediction-options',headers=headers,params={'q':'acme 20000mah'}))
    key=options['products'][0]['product_key']
    prediction=ok(client.post('/ml/predict',headers=headers,json={'product_key':key,'dataset_id':dataset['dataset_id']}))
    assert len(prediction['ranking'])==2
    assert all(0<=row['opportunity_score']<=100 for row in prediction['ranking'])
    assert prediction['model']['version']=='v1' and 'DEMO' in prediction['warning']
    assert prediction['data_provenance']['source_types']==['demo']
    trends=ok(client.get('/analytics/trends',headers=headers,params={'product_key':key,'source_type':'demo'}))
    assert trends['status']=='available' and trends['total_series']==2
    comparison=ok(client.get('/analytics/platform-comparison',headers=headers,params={'product_key':key}))
    assert comparison['status']=='available'
    saved=[p['opportunity'] for g in comparison['groups'] for p in g['platforms'] if p['opportunity']]
    assert len(saved)==2 and all(s['model_version']=='v1' for s in saved)
    history=ok(client.get('/ml/predictions',headers=headers))
    assert history['total']==1 and history['items'][0]['id']==prediction['id']
    assert ok(client.get('/analytics/summary',headers=headers))['total_predictions']==1
    other=ok(client.post('/auth/register',json={'email':'other@example.com','password':'marketpulse1'}),201)
    other_headers={'Authorization':'Bearer '+other['access_token']}
    assert client.get('/ml/predictions/'+str(prediction['id']),headers=other_headers).status_code==404
    assert client.get('/ml/predictions').status_code==401
# A second startup migrates idempotently and reads the immutable JSON response.
with TestClient(app) as client:
    restored=ok(client.get('/ml/predictions/'+str(prediction['id']),headers=headers))
    assert restored==prediction
    assert ok(client.get('/data/status',headers=headers))['total_snapshots']==481
engine.dispose()
print('fresh API journey passed: auth, ingestion, dataset, training, prediction, score, analytics, history, isolation, restart')
'''
    result=subprocess.run([sys.executable,'-B','-c',script],cwd=Path(__file__).resolve().parents[1],env=env,text=True,capture_output=True,timeout=180)
    assert result.returncode==0, result.stdout+'\n'+result.stderr
