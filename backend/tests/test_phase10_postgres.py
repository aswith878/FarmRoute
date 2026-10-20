import os
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from fastapi.testclient import TestClient
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from app.main import app
from app.models import ProduceBatch,User,AlternativeAllocation,Transaction
import test_phase9_postgres


@unittest.skipUnless(os.getenv('AGRIRoute_POSTGRES_TESTS')=='1','Enable isolated PostgreSQL tests')
class ProcessorConcurrencyTests(unittest.TestCase):
    setUpClass=classmethod(test_phase9_postgres.PostgresConcurrencyTests.setUpClass.__func__)
    tearDownClass=classmethod(test_phase9_postgres.PostgresConcurrencyTests.tearDownClass.__func__)
    tearDown=test_phase9_postgres.PostgresConcurrencyTests.tearDown

    def setUp(self):
        test_phase9_postgres.PostgresConcurrencyTests.setUp(self)
        with Session(self.test_engine) as db:
            db.get(ProduceBatch,self.batch_id).visible_condition='FRESH'
            processor=User(name='Isolated processor',email=uuid.uuid4().hex+'@test.example',role='PROCESSOR')
            buyer=User(name='Isolated buyer',email=uuid.uuid4().hex+'@test.example',role='BUYER')
            # LIKE tables retain public enum types; individual inserts avoid
            # bulk INSERT enum casts into the translated temporary schema.
            db.add(processor)
            db.flush()
            db.add(buyer)
            db.flush()
            db.commit()
            processor_id,buyer_id=processor.id,buyer.id
        with TestClient(app) as client:
            response=client.post(f'/produce/{self.batch_id}/rerouting')
            self.assertEqual(response.status_code,200,response.text)
            self.case_id=response.json()['id']
            response=client.post('/processor-requirements',json={'processor_id':processor_id,'crop_name':'Tomato','required_quantity_kg':'150','minimum_acceptable_quality':'A','acceptable_produce_conditions':['FRESH'],'intended_utilization':'FOOD_PROCESSING','minimum_price_per_kg':'10','maximum_price_per_kg':'30'})
            self.assertEqual(response.status_code,201,response.text)
            self.req_id=response.json()['id']
            response=client.post(f'/routing-cases/{self.case_id}/suitability',json={'intended_utilization':'FOOD_PROCESSING','confirmed_condition':'FRESH','suitable':True,'assessed_by':'Synthetic fixture','assessment_notes':'Isolated synthetic assessment; not a real-world food safety claim.'})
            self.assertEqual(response.status_code,200,response.text)
            self.buyer_req=client.post('/buyer-requirements',json={'buyer_id':buyer_id,'crop_name':'Tomato','required_quantity_kg':'150','minimum_quality':'A','minimum_price_per_kg':'10','maximum_price_per_kg':'30'}).json()['id']

    def run_parallel(self,requests):
        barrier=Barrier(len(requests))
        def run(request):
            path,payload,headers=request
            with TestClient(app) as client:
                barrier.wait(timeout=20)
                response=client.post(path,json=payload,headers=headers)
                return response.status_code,response.json()
        with ThreadPoolExecutor(max_workers=len(requests)) as workers:
            return list(workers.map(run,requests))

    def allocation_request(self,key,qty='100'):
        return (f'/routing-cases/{self.case_id}/accept',{'processor_requirement_id':self.req_id,'accepted_quantity_kg':qty,'price_per_kg':'25'},{'Idempotency-Key':key})

    def test_concurrent_acceptance_no_overselling(self):
        results=self.run_parallel([self.allocation_request('a'),self.allocation_request('b')])
        self.assertEqual(sorted(status for status,_ in results),[200,409],results)
        with Session(self.test_engine) as db:
            batch=db.get(ProduceBatch,self.batch_id)
            self.assertEqual(batch.remaining_quantity_kg,50)
            self.assertEqual(batch.rerouted_quantity_kg,100)
            self.assertEqual(batch.sold_quantity_kg,0)
            self.assertEqual(db.scalar(select(func.count()).select_from(AlternativeAllocation).where(AlternativeAllocation.routing_case_id==self.case_id)),1)

    def test_concurrent_idempotent_retry(self):
        request=self.allocation_request('shared-key','150')
        results=self.run_parallel([request,request,request,request])
        self.assertTrue(all(status==200 for status,_ in results),results)
        self.assertEqual(len({row['id'] for _,row in results}),1)
        with Session(self.test_engine) as db:
            batch=db.get(ProduceBatch,self.batch_id)
            self.assertEqual(batch.remaining_quantity_kg,0)
            self.assertEqual(batch.rerouted_quantity_kg,150)

    def test_primary_and_alternative_share_inventory_lock(self):
        primary=('/transactions/accept',{'produce_batch_id':self.batch_id,'buyer_requirement_id':self.buyer_req,'quantity_kg':'100'},{})
        results=self.run_parallel([primary,self.allocation_request('alternative')])
        self.assertEqual(sum(status in (200,201) for status,_ in results),1,results)
        self.assertEqual(sum(status==409 for status,_ in results),1,results)
        with Session(self.test_engine) as db:
            batch=db.get(ProduceBatch,self.batch_id)
            self.assertEqual(batch.remaining_quantity_kg,50)
            self.assertEqual(batch.sold_quantity_kg+batch.rerouted_quantity_kg,100)
            self.assertEqual(batch.initial_quantity_kg,batch.remaining_quantity_kg+batch.sold_quantity_kg+batch.rerouted_quantity_kg)
