"""Real signed-token tests: no authentication dependency bypasses."""
import secrets
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch
import jwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.database import Base, get_db
from app.core.auth import get_identity_db, enforce_owner
from app.core.security import create_token, hash_password, settings, ISSUER, AUDIENCE
from app.main import app
from app.models import User, ProduceBatch, Transaction, AlternativeAllocation, ProcessorRequirement
from app.models.enums import UserRole
from app.services.transactions import accept_transaction
from app.services.alternative_acceptance_service import accept_alternative
from app.schemas.transaction import TransactionAcceptRequest
from app.schemas.processor import AlternativeAcceptRequest
from fastapi import HTTPException


class AuthenticationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password = secrets.token_urlsafe(24)
        cls.encoded = hash_password(cls.password)

    def setUp(self):
        self.engine = create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        def db_session():
            with Session(self.engine) as db:
                try:
                    yield db
                except Exception:
                    db.rollback()
                    raise
        self.previous = dict(app.dependency_overrides)
        app.dependency_overrides.clear()
        app.dependency_overrides[get_db] = db_session
        app.dependency_overrides[get_identity_db] = db_session
        self.users = {}
        self.headers = {}
        with Session(self.engine) as db:
            for key,role in [('farmer','FARMER'),('farmer2','FARMER'),('buyer','BUYER'),('buyer2','BUYER'),('processor','PROCESSOR'),('processor2','PROCESSOR'),('admin','ADMIN')]:
                user = User(name=key,email=key+'@test.example',role=role,password_hash=self.encoded)
                db.add(user)
                db.flush()
                self.users[key] = user.id
                self.headers[key] = {'Authorization':'Bearer '+create_token(user.id)['access_token']}
            db.commit()
        self.client = TestClient(app)
        self.counter = 0
        def code(*args):
            self.counter += 1
            return f'TEST-{self.counter}'
        self.code_patch = patch('app.routes.produce.generate_batch_code',side_effect=code)
        self.code_patch.start()

    def tearDown(self):
        self.code_patch.stop()
        self.client.close()
        app.dependency_overrides.clear()
        app.dependency_overrides.update(self.previous)
        self.engine.dispose()

    def request(self,method,url,role='admin',**kwargs):
        return self.client.request(method,url,headers=self.headers[role],**kwargs)

    def batch(self,role='farmer',**changes):
        payload = dict(farmer_id=self.users[role],crop_name='Tomato',initial_quantity_kg='1000',expected_price_per_kg='25',harvest_date='2026-10-05',quality_grade='A',risk_level='CRITICAL',visible_condition='FRESH') | changes
        response = self.request('POST','/produce',role,json=payload)
        self.assertEqual(response.status_code,201,response.text)
        return response.json()

    def requirement(self,role='buyer'):
        response = self.request('POST','/buyer-requirements',role,json=dict(buyer_id=self.users[role],crop_name='Tomato',required_quantity_kg='500',minimum_quality='A',minimum_price_per_kg='20',maximum_price_per_kg='30'))
        self.assertEqual(response.status_code,201,response.text)
        return response.json()

    def processor_requirement(self,role='processor'):
        response = self.request('POST','/processor-requirements',role,json=dict(processor_id=self.users[role],crop_name='Tomato',required_quantity_kg='200',minimum_acceptable_quality='A',acceptable_produce_conditions=['FRESH'],intended_utilization='FOOD_PROCESSING',minimum_price_per_kg='20',maximum_price_per_kg='30'))
        self.assertEqual(response.status_code,201,response.text)
        return response.json()

    def case(self,batch):
        response = self.request('POST',f'/produce/{batch["id"]}/rerouting','farmer')
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    def assessment(self,case,req,role='processor'):
        return self.request('POST',f'/routing-cases/{case["id"]}/suitability',role,json=dict(processor_requirement_id=req['id'],intended_utilization='FOOD_PROCESSING',confirmed_condition='FRESH',suitable=True,assessed_by='untrusted submitted name',assessment_notes='Isolated human assessment'))

    def token_response(self,claims,**overrides):
        secret,_ = settings()
        now = datetime.now(timezone.utc)
        data = dict(sub=str(self.users['farmer']),iat=now,exp=now+timedelta(minutes=1),iss=ISSUER,aud=AUDIENCE) | claims
        token = jwt.encode(data,overrides.get('secret',secret),algorithm=overrides.get('algorithm','HS256'))
        return self.client.get('/auth/me',headers={'Authorization':'Bearer '+token})

    def test_registration_hash_and_safe_profile(self):
        response = self.client.post('/auth/register',json=dict(name='New Farmer',email='NEW@TEST.EXAMPLE',password=self.password,role='FARMER',phone='123',location_name='Village'))
        self.assertEqual(response.status_code,201,response.text)
        self.assertEqual(response.json()['email'],'new@test.example')
        self.assertNotIn('password',response.text)
        with Session(self.engine) as db:
            row = db.get(User,response.json()['id'])
            self.assertTrue(row.password_hash.startswith('$argon2id$'))
            self.assertNotEqual(row.password_hash,self.password)

    def test_public_buyer_and_processor_registration(self):
        for role in ['BUYER','PROCESSOR']:
            response = self.client.post('/auth/register',json=dict(name=role,email=role+'@new.example',password=self.password,role=role))
            self.assertEqual(response.status_code,201,response.text)

    def test_successful_login_me_and_last_login(self):
        response = self.client.post('/auth/login',json={'email':'FARMER@TEST.EXAMPLE','password':self.password})
        self.assertEqual(response.status_code,200,response.text)
        token = response.json()
        self.assertEqual(token['token_type'],'bearer')
        self.assertGreater(token['expires_in'],0)
        profile = self.client.get('/auth/me',headers={'Authorization':'Bearer '+token['access_token']})
        self.assertEqual(profile.json()['id'],self.users['farmer'])
        self.assertNotIn('password_hash',profile.text)
        with Session(self.engine) as db:
            self.assertIsNotNone(db.get(User,self.users['farmer']).last_login_at)

    def test_wrong_unknown_and_legacy_credentials(self):
        with Session(self.engine) as db:
            db.add(User(name='Legacy',email='legacy@test.example',role='FARMER'))
            db.commit()
        results = [self.client.post('/auth/login',json={'email':email,'password':'incorrect-password'}) for email in ['farmer@test.example','unknown@test.example','legacy@test.example']]
        self.assertEqual([r.status_code for r in results],[401]*3)
        self.assertEqual(len({r.text for r in results}),1)

    def test_duplicate_email_case_insensitive(self):
        response = self.client.post('/auth/register',json=dict(name='Duplicate',email='FARMER@TEST.EXAMPLE',password=self.password,role='BUYER'))
        self.assertEqual(response.status_code,409)

    def test_public_admin_registration_rejected(self):
        response = self.client.post('/auth/register',json=dict(name='Admin',email='newadmin@test.example',password=self.password,role='ADMIN'))
        self.assertEqual(response.status_code,403)

    def test_password_length_and_sensitive_validation(self):
        for password in ['short',self.password*10]:
            response = self.client.post('/auth/register',json=dict(name='Invalid',email='invalid@test.example',password=password,role='FARMER'))
            self.assertEqual(response.status_code,422)
            self.assertNotIn(password,response.text)

    def test_expired_token(self):
        self.assertEqual(self.token_response({'exp':datetime.now(timezone.utc)-timedelta(seconds=1)}).status_code,401)

    def test_invalid_signature_issuer_audience_and_subject(self):
        for claims in [{'iss':'other'},{'aud':'other'},{'sub':'bad'},{'sub':'0'}]:
            self.assertEqual(self.token_response(claims).status_code,401)
        self.assertEqual(self.token_response({},secret=secrets.token_urlsafe(48)).status_code,401)
        self.assertEqual(self.client.get('/auth/me',headers={'Authorization':'Bearer malformed'}).status_code,401)

    def test_missing_expiration_and_wrong_algorithm(self):
        secret,_ = settings()
        token = jwt.encode({'sub':str(self.users['farmer'])},secret,algorithm='HS256')
        self.assertEqual(self.client.get('/auth/me',headers={'Authorization':'Bearer '+token}).status_code,401)
        self.assertEqual(self.token_response({},algorithm='HS384').status_code,401)

    def test_missing_tokens_all_business_routes(self):
        paths = self.client.get('/openapi.json').json()['paths']
        for path,operations in paths.items():
            if path.startswith(('/auth','/health')):
                continue
            concrete = path
            for field in ['user_id','batch_id','requirement_id','transaction_id','case_id','allocation_id']:
                concrete = concrete.replace('{'+field+'}','1')
            for method in operations:
                response = self.client.request(method,concrete,json={} if method in {'post','put'} else None)
                self.assertEqual(response.status_code,401,(method,path,response.text))

    def test_inactive_account_login_and_existing_token(self):
        with Session(self.engine) as db:
            db.get(User,self.users['farmer']).is_active = False
            db.commit()
        self.assertEqual(self.request('GET','/auth/me','farmer').status_code,401)
        self.assertEqual(self.client.post('/auth/login',json={'email':'farmer@test.example','password':self.password}).status_code,401)

    def test_unknown_user_token(self):
        self.assertEqual(self.token_response({'sub':'999999'}).status_code,401)

    def test_legacy_account_token_rejected(self):
        with Session(self.engine) as db:
            db.get(User,self.users['farmer']).password_hash = None
            db.commit()
        self.assertEqual(self.request('GET','/auth/me','farmer').status_code,401)

    def test_role_is_loaded_from_database(self):
        with Session(self.engine) as db:
            db.get(User,self.users['farmer']).role = UserRole.BUYER
            db.commit()
        self.assertEqual(self.request('GET','/users','farmer').status_code,403)
        self.assertEqual(self.request('GET','/auth/me','farmer').json()['role'],'BUYER')

    def test_farmer_own_produce_update_matching_timeline(self):
        batch = self.batch()
        url = f'/produce/{batch["id"]}'
        for suffix in ['', '/timeline','/routing-readiness']:
            self.assertEqual(self.request('GET',url+suffix,'farmer').status_code,200)
        self.assertEqual(self.request('GET',f'/matches/produce/{batch["id"]}','farmer').status_code,200)
        self.assertEqual(self.request('PUT',url,'farmer',json={'notes':'Own update'}).status_code,200)
        self.assertEqual(len(self.request('GET','/produce','farmer').json()),1)

    def test_farmer_cross_access_and_owner_spoof(self):
        batch = self.batch('farmer2')
        for suffix in ['', '/timeline','/routing-readiness']:
            self.assertEqual(self.request('GET',f'/produce/{batch["id"]}'+suffix,'farmer').status_code,403)
        self.assertEqual(self.request('PUT',f'/produce/{batch["id"]}','farmer',json={'notes':'attack'}).status_code,403)
        self.assertEqual(self.request('POST','/produce','farmer',json={'farmer_id':self.users['farmer2']}).status_code,403)
        self.assertEqual(self.request('GET',f'/produce?farmer_id={self.users["farmer2"]}','farmer').json(),[])

    def test_users_restricted_and_privilege_escalation_rejected(self):
        self.assertEqual(self.request('GET','/users','farmer').status_code,403)
        self.assertEqual(self.request('GET',f'/users/{self.users["farmer"]}','farmer').status_code,200)
        self.assertEqual(self.request('GET',f'/users/{self.users["buyer"]}','farmer').status_code,403)
        self.assertEqual(self.request('PUT',f'/users/{self.users["farmer"]}','farmer',json={'is_active':True}).status_code,403)
        self.assertEqual(self.request('POST','/users','farmer',json={}).status_code,403)
        self.assertEqual(self.request('PUT',f'/users/{self.users["buyer"]}',json={'role':'ADMIN'}).status_code,422)

    def test_buyer_own_requirement_and_eligible_opportunities(self):
        req = self.requirement()
        batch = self.batch()
        other = self.batch('farmer2',crop_name='Onion')
        self.assertEqual(self.request('PUT',f'/buyer-requirements/{req["id"]}','buyer',json={'maximum_price_per_kg':'31'}).status_code,200)
        self.assertEqual([r['id'] for r in self.request('GET','/produce','buyer').json()],[batch['id']])
        self.assertEqual(self.request('GET',f'/produce/{other["id"]}','buyer').status_code,403)
        self.assertEqual(self.request('GET',f'/produce/{batch["id"]}/timeline','buyer').status_code,403)

    def test_buyer_cross_requirement_and_role_restrictions(self):
        req = self.requirement('buyer2')
        self.assertEqual(self.request('GET',f'/buyer-requirements/{req["id"]}','buyer').status_code,403)
        self.assertEqual(self.request('PUT',f'/buyer-requirements/{req["id"]}','buyer',json={'maximum_price_per_kg':'40'}).status_code,403)
        self.assertEqual(self.request('POST','/buyer-requirements','buyer',json={'buyer_id':self.users['buyer2']}).status_code,403)
        self.assertEqual(self.request('GET','/buyer-requirements','buyer').json(),[])

    def test_buyer_requirement_cancellation_is_owner_scoped_and_one_way(self):
        req = self.requirement('buyer2')
        self.assertEqual(self.request('POST',f'/buyer-requirements/{req["id"]}/cancel','buyer').status_code,403)
        cancelled = self.request('POST',f'/buyer-requirements/{req["id"]}/cancel','buyer2')
        self.assertEqual(cancelled.status_code,200,cancelled.text)
        self.assertEqual(cancelled.json()['status'],'CANCELLED')
        self.assertEqual(self.request('POST',f'/buyer-requirements/{req["id"]}/cancel','buyer2').status_code,409)
        self.assertEqual(self.request('POST','/produce','buyer',json={}).status_code,403)

    def test_primary_acceptance_preserves_arithmetic_and_scoped_history(self):
        batch,req = self.batch(),self.requirement()
        response = self.request('POST','/transactions/accept','buyer',json={'produce_batch_id':batch['id'],'buyer_requirement_id':req['id'],'quantity_kg':'125'})
        self.assertEqual(response.status_code,201,response.text)
        updated = self.request('GET',f'/produce/{batch["id"]}').json()
        self.assertEqual((updated['sold_quantity_kg'],updated['remaining_quantity_kg'],updated['rerouted_quantity_kg']),('125.000','875.000','0.000'))
        self.assertEqual(len(self.request('GET','/transactions','buyer').json()),1)
        self.assertEqual(self.request('GET','/transactions','buyer2').json(),[])
        self.assertEqual(self.request('GET',f'/transactions/{response.json()["id"]}','buyer2').status_code,403)
        self.assertEqual(len(self.request('GET','/transactions','farmer').json()),1)

    def test_unauthorized_primary_acceptance_no_side_effects(self):
        batch,req = self.batch(),self.requirement('buyer2')
        before = self.request('GET',f'/produce/{batch["id"]}').json()
        response = self.request('POST','/transactions/accept','buyer',json={'produce_batch_id':batch['id'],'buyer_requirement_id':req['id'],'quantity_kg':'100'})
        self.assertEqual(response.status_code,403)
        self.assertEqual(self.request('GET',f'/produce/{batch["id"]}').json(),before)
        self.assertEqual(self.request('GET','/transactions').json(),[])

    def test_service_primary_owner_check_independent_of_route(self):
        batch,req = self.batch(),self.requirement('buyer2')
        with Session(self.engine) as db:
            actor = User(id=self.users['buyer'],role=UserRole.BUYER)
            db.info['actor'] = actor
            with self.assertRaises(HTTPException) as error:
                accept_transaction(db,TransactionAcceptRequest(produce_batch_id=batch['id'],buyer_requirement_id=req['id'],quantity_kg='1'))
            self.assertEqual(error.exception.status_code,403)

    def test_processor_own_requirements_updates_and_discovery(self):
        req = self.processor_requirement()
        case = self.case(self.batch())
        self.assertEqual(self.request('GET',f'/processor-requirements/{req["id"]}','processor').status_code,200)
        self.assertEqual(self.request('PUT',f'/processor-requirements/{req["id"]}','processor',json={'maximum_price_per_kg':'35'}).status_code,200)
        self.assertEqual([r['id'] for r in self.request('GET','/routing-cases','processor').json()],[case['id']])
        self.assertEqual(self.request('GET','/routing-cases','processor2').json(),[])

    def test_processor_cross_requirements_and_owner_spoof(self):
        req = self.processor_requirement('processor2')
        self.assertEqual(self.request('GET',f'/processor-requirements/{req["id"]}','processor').status_code,403)
        self.assertEqual(self.request('PUT',f'/processor-requirements/{req["id"]}','processor',json={'maximum_price_per_kg':'35'}).status_code,403)
        self.assertEqual(self.request('POST','/processor-requirements','processor',json={'processor_id':self.users['processor2']}).status_code,403)
        self.assertEqual(self.request('GET','/processor-requirements','processor').json(),[])

    def test_processor_requirement_cancellation_is_owner_scoped_and_one_way(self):
        req = self.processor_requirement('processor2')
        self.assertEqual(self.request('POST',f'/processor-requirements/{req["id"]}/cancel','processor').status_code,403)
        cancelled = self.request('POST',f'/processor-requirements/{req["id"]}/cancel','processor2')
        self.assertEqual(cancelled.status_code,200,cancelled.text)
        self.assertEqual(cancelled.json()['status'],'CANCELLED')
        self.assertEqual(self.request('POST',f'/processor-requirements/{req["id"]}/cancel','processor2').status_code,409)

    def test_suitability_owned_scoped_and_server_attributed(self):
        case = self.case(self.batch())
        req,other = self.processor_requirement(),self.processor_requirement('processor2')
        response = self.assessment(case,req)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['assessor_user_id'],self.users['processor'])
        self.assertEqual(response.json()['assessed_by'],'processor')
        self.assertEqual(self.assessment(case,other).status_code,403)
        matches = self.request('GET',f'/routing-cases/{case["id"]}/processor-matches','processor').json()['matches']
        self.assertEqual([r['processor_requirement_id'] for r in matches],[req['id']])
        self.assertEqual(self.request('GET',f'/routing-cases/{case["id"]}/processor-matches','processor2').json()['matches'],[])
        details = self.request('GET',f'/routing-cases/{case["id"]}','processor2').json()['trigger_details']
        self.assertEqual(details['processing_suitability_by_requirement'],{})

    def test_unscoped_processor_suitability_rejected(self):
        case = self.case(self.batch())
        self.processor_requirement()
        response = self.request('POST',f'/routing-cases/{case["id"]}/suitability','processor',json=dict(intended_utilization='FOOD_PROCESSING',confirmed_condition='FRESH',suitable=True,assessed_by='x',assessment_notes='x'))
        self.assertEqual(response.status_code,422)

    def test_processor_acceptance_and_duplicate_inventory(self):
        batch = self.batch()
        case,req = self.case(batch),self.processor_requirement()
        self.assertEqual(self.assessment(case,req).status_code,200)
        payload = dict(processor_requirement_id=req['id'],accepted_quantity_kg='125',price_per_kg='25')
        headers = self.headers['processor'] | {'Idempotency-Key':'owned-key'}
        first = self.client.post(f'/routing-cases/{case["id"]}/accept',headers=headers,json=payload)
        retry = self.client.post(f'/routing-cases/{case["id"]}/accept',headers=headers,json=payload)
        self.assertEqual(first.status_code,200,first.text)
        self.assertEqual(first.json(),retry.json())
        updated = self.request('GET',f'/produce/{batch["id"]}').json()
        self.assertEqual((updated['sold_quantity_kg'],updated['remaining_quantity_kg'],updated['rerouted_quantity_kg']),('0.000','875.000','125.000'))
        self.assertEqual(self.request('GET','/transactions').json(),[])
        self.assertEqual(self.request('GET','/alternative-allocations','processor2').json(),[])
        self.assertEqual(self.request('GET',f'/alternative-allocations/{first.json()["id"]}','processor2').status_code,403)

    def test_unauthorized_alternative_acceptance_no_side_effects(self):
        batch = self.batch()
        case,req = self.case(batch),self.processor_requirement('processor2')
        before = self.request('GET',f'/produce/{batch["id"]}').json()
        response = self.client.post(f'/routing-cases/{case["id"]}/accept',headers=self.headers['processor'] | {'Idempotency-Key':'attack'},json={'processor_requirement_id':req['id'],'accepted_quantity_kg':'10'})
        self.assertEqual(response.status_code,403)
        self.assertEqual(self.request('GET',f'/produce/{batch["id"]}').json(),before)
        self.assertEqual(self.request('GET','/alternative-allocations').json(),[])

    def test_service_alternative_owner_check_independent_of_route(self):
        case = self.case(self.batch())
        req = self.processor_requirement('processor2')
        with Session(self.engine) as db:
            db.info['actor'] = User(id=self.users['processor'],role=UserRole.PROCESSOR)
            with self.assertRaises(HTTPException) as error:
                accept_alternative(db,case['id'],AlternativeAcceptRequest(processor_requirement_id=req['id'],accepted_quantity_kg='10'),'service-owner')
            self.assertEqual(error.exception.status_code,403)

    def test_admin_access_and_business_role_restrictions(self):
        self.assertEqual(len(self.request('GET','/users').json()),7)
        self.assertEqual(self.request('PUT',f'/users/{self.users["buyer"]}',json={'is_active':False}).status_code,200)
        for role in ['farmer','buyer','processor']:
            self.assertEqual(self.request('GET','/users',role).status_code,403 if role!='buyer' else 401)
        self.assertEqual(self.request('POST','/transactions/accept','processor',json={}).status_code,403)
        self.assertEqual(self.request('GET','/buyer-requirements','processor').status_code,403)

    def test_health_docs_and_swagger_security(self):
        self.assertEqual(self.client.get('/health').json(),{'status':'ok','service':'AgriRoute API'})
        self.assertEqual(self.client.get('/docs').status_code,200)
        schema = self.client.get('/openapi.json').json()
        self.assertEqual(schema['components']['securitySchemes']['HTTPBearer']['scheme'],'bearer')
        for path,operations in schema['paths'].items():
            if path.startswith('/health') or path in ['/auth/login','/auth/register']:
                continue
            for operation in operations.values():
                self.assertIn({'HTTPBearer':[]},operation['security'])

    def test_config_rejects_missing_secret_and_invalid_expiry(self):
        with patch.dict('os.environ',{'JWT_SECRET':''}):
            with self.assertRaises(RuntimeError):
                settings()
        with patch.dict('os.environ',{'JWT_ACCESS_TOKEN_EXPIRE_MINUTES':'0'}):
            with self.assertRaises(RuntimeError):
                settings()

    def test_reusable_owner_and_role_dependency(self):
        from app.core.auth import require_roles
        check = require_roles(UserRole.ADMIN)
        with self.assertRaises(HTTPException) as error:
            check(User(id=1,role=UserRole.FARMER))
        self.assertEqual(error.exception.status_code,403)
        admin = User(id=1,role=UserRole.ADMIN)
        self.assertIs(check(admin),admin)
        enforce_owner(admin,999,UserRole.FARMER)

    def test_local_credential_activation_preserves_user_and_inventory(self):
        import sys
        from sqlalchemy.orm import sessionmaker
        from scripts.activate_user import main
        batch = self.batch()
        with Session(self.engine) as db:
            user = db.get(User,self.users['farmer'])
            user.password_hash = None
            db.commit()
        before = self.request('GET',f'/produce/{batch["id"]}').json()
        new_password = secrets.token_urlsafe(24)
        with patch.object(sys,'argv',['activate_user',str(self.users['farmer'])]), patch('scripts.activate_user.sys.stdin.isatty',return_value=True), patch('scripts.activate_user.getpass.getpass',side_effect=[new_password,new_password]), patch('scripts.activate_user.SessionLocal',sessionmaker(bind=self.engine)), patch('builtins.print'):
            main()
        login = self.client.post('/auth/login',json={'email':'farmer@test.example','password':new_password})
        self.assertEqual(login.status_code,200,login.text)
        self.assertEqual(self.request('GET',f'/produce/{batch["id"]}').json(),before)

    def test_password_whitespace_is_not_silently_modified(self):
        password = ' '+self.password+' '
        self.assertEqual(self.client.post('/auth/register',json=dict(name='Whitespace',email='space@test.example',password=password,role='BUYER')).status_code,201)
        self.assertEqual(self.client.post('/auth/login',json={'email':'space@test.example','password':password}).status_code,200)
        self.assertEqual(self.client.post('/auth/login',json={'email':'space@test.example','password':password.strip()}).status_code,401)

    def test_local_admin_bootstrap(self):
        from sqlalchemy.orm import sessionmaker
        from scripts.create_admin import main
        password = secrets.token_urlsafe(24)
        with patch('scripts.create_admin.sys.stdin.isatty',return_value=True), patch('builtins.input',side_effect=['Local Administrator','localadmin@test.example']), patch('scripts.create_admin.getpass.getpass',side_effect=[password,password]), patch('scripts.create_admin.SessionLocal',sessionmaker(bind=self.engine)), patch('builtins.print'):
            main()
        login = self.client.post('/auth/login',json={'email':'localadmin@test.example','password':password})
        self.assertEqual(login.status_code,200,login.text)
        response = self.client.get('/users',headers={'Authorization':'Bearer '+login.json()['access_token']})
        self.assertEqual(response.status_code,200)
        self.assertEqual(len(response.json()),8)

    def test_local_credentials_require_interactive_terminal(self):
        import sys
        from scripts.activate_user import main as activate
        from scripts.create_admin import main as create_admin
        with patch.object(sys,'argv',['activate_user','1']), patch('sys.stdin.isatty',return_value=False), patch('getpass.getpass') as prompt:
            for command in [activate,create_admin]:
                with self.assertRaises(SystemExit):
                    command()
            prompt.assert_not_called()
