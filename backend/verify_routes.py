import os, json
os.environ['CSV_OUTPUT_DIR'] = r'c:\Users\DELL\Desktop\ET gen AI Hackthon\Project\backend\data\macro_events'
from api.main import app
from fastapi.testclient import TestClient

client = TestClient(app)
for path in ['/api/health','/api/risk-corridors','/api/news-feed','/api/auto-alerts','/api/corridor-brief?corridor=hormuz']:
    try:
        r = client.get(path)
        print(path, '=>', r.status_code)
        payload = r.json()
        if isinstance(payload, dict):
            print('keys:', list(payload.keys())[:10])
    except Exception as e:
        print(path, 'ERR', e)
