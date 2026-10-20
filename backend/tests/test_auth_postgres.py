"""JWT and unique registration checks against an isolated Supabase schema."""
import os
import secrets
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from fastapi.testclient import TestClient
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from app.core.auth import get_current_user
from app.main import app
from app.models import User
import test_phase9_postgres


@unittest.skipUnless(os.getenv('AGRIRoute_POSTGRES_TESTS')=='1','Enable isolated PostgreSQL tests')
class AuthPostgresTests(unittest.TestCase):
    setUpClass=classmethod(test_phase9_postgres.PostgresConcurrencyTests.setUpClass.__func__)
    tearDownClass=classmethod(test_phase9_postgres.PostgresConcurrencyTests.tearDownClass.__func__)
    tearDown=test_phase9_postgres.PostgresConcurrencyTests.tearDown

    def setUp(self):
        test_phase9_postgres.PostgresConcurrencyTests.setUp(self)
        app.dependency_overrides.pop(get_current_user,None)

    def test_concurrent_duplicate_registration(self):
        email=uuid.uuid4().hex+'@auth.example'
        payload=dict(name='Isolated account',email=email,password=secrets.token_urlsafe(24),role='BUYER')
        barrier=Barrier(4)
        def register(_):
            with TestClient(app) as client:
                barrier.wait(timeout=20)
                return client.post('/auth/register',json=payload).status_code
        with ThreadPoolExecutor(max_workers=4) as workers:
            results=list(workers.map(register,range(4)))
        self.assertEqual(sorted(results),[201,409,409,409])
        with Session(self.test_engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(User).where(User.email==email)),1)

    def test_register_login_protected_profile_and_role(self):
        payload=dict(name='Isolated farmer',email=uuid.uuid4().hex+'@auth.example',password=secrets.token_urlsafe(24),role='FARMER')
        with TestClient(app) as client:
            registered=client.post('/auth/register',json=payload)
            self.assertEqual(registered.status_code,201,registered.text)
            logged=client.post('/auth/login',json={key:payload[key] for key in ['email','password']})
            self.assertEqual(logged.status_code,200,logged.text)
            headers={'Authorization':'Bearer '+logged.json()['access_token']}
            me=client.get('/auth/me',headers=headers)
            self.assertEqual(me.json()['id'],registered.json()['id'])
            self.assertNotIn('password',me.text)
            self.assertEqual(client.get('/users',headers=headers).status_code,403)
            self.assertEqual(client.get('/produce',headers=headers).json(),[])
