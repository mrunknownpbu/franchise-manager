import os
os.environ['DATABASE_PATH']='./test-api.db'; os.environ['ADMIN_PASSWORD']='test-password'
from fastapi.testclient import TestClient
from app.main import app

def test_health_and_auth():
 with TestClient(app) as client:
  assert client.get('/api/health').status_code == 200
  response=client.post('/api/auth/login',json={'username':'admin','password':'test-password'})
  assert response.status_code == 200
  headers={'Authorization':'Bearer '+response.json()['token']}
  assert client.get('/api/collections',headers=headers).status_code == 200
