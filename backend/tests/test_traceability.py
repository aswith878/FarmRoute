import unittest
from decimal import Decimal
from datetime import date,datetime,timezone
from unittest.mock import patch
from sqlalchemy import select,func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
import test_crud
import test_phase10
from app.models import BatchEvent,ProduceBatch,Transaction,RoutingCase


class TraceabilityTests(unittest.TestCase):
    setUp=test_crud.CrudTests.setUp
    tearDown=test_crud.CrudTests.tearDown

    def batch(self,**changes):
        return self.client.post('/produce',json=self.produce|changes).json()['id']

    def events(self,batch):
        response=self.client.get(f'/produce/{batch}/timeline')
        self.assertEqual(response.status_code,200,response.text)
        return response.json()['events']

    def count(self,batch):
        with Session(self.engine) as db:
            return db.scalar(select(func.count()).select_from(BatchEvent).where(BatchEvent.produce_batch_id==batch))

    def sell(self,batch,quantity='100'):
        req=self.client.post('/buyer-requirements',json=self.requirement|{'required_quantity_kg':quantity}).json()['id']
        return self.client.post('/transactions/accept',json={'produce_batch_id':batch,'buyer_requirement_id':req,'quantity_kg':quantity})

    def test_batch_creation_event(self):
        batch=self.batch()
        events=self.events(batch)
        self.assertEqual(len(events),1)
        self.assertEqual(events[0]['event_type'],'BATCH_CREATED')
        self.assertEqual(events[0]['history_origin'],'recorded_event')
        self.assertEqual(events[0]['quantity_kg'],'1000.000')

    def test_partial_primary_sale_event(self):
        batch=self.batch()
        self.assertEqual(self.sell(batch).status_code,201)
        events=self.events(batch)
        sale=next(event for event in events if event['event_type']=='PRIMARY_SALE_ACCEPTED')
        self.assertEqual(sale['quantity_kg'],'100.000')
        self.assertEqual(sale['previous_status'],'ACTIVE')
        self.assertEqual(sale['new_status'],'PARTIALLY_SOLD')
        self.assertNotIn('BATCH_FULLY_ALLOCATED',[event['event_type'] for event in events])

    def test_complete_primary_sale(self):
        batch=self.batch()
        self.assertEqual(self.sell(batch,'1000').status_code,201)
        types=[event['event_type'] for event in self.events(batch)]
        self.assertEqual(types.count('BATCH_FULLY_ALLOCATED'),1)
        self.assertNotIn('BATCH_FULLY_UTILIZED',types)

    def test_matching_attempt_and_duplicate_cooldown(self):
        batch=self.batch()
        self.client.post(f'/produce/{batch}/matching-attempts')
        first=self.events(batch)
        self.client.post(f'/produce/{batch}/matching-attempts')
        self.client.get(f'/matches/produce/{batch}')
        self.client.get(f'/produce/{batch}/routing-readiness')
        self.assertEqual(self.events(batch),first)
        self.assertEqual(sum(event['event_type']=='PRIMARY_MATCH_ATTEMPTED' for event in first),1)

    def test_rejection_event_deduplicated(self):
        batch=self.batch()
        req=self.client.post('/buyer-requirements',json=self.requirement).json()['id']
        payload={'buyer_requirement_id':req,'rejected_quantity_kg':'100','reason':'COSMETIC_DEFECT'}
        for _ in range(2):
            self.client.post(f'/produce/{batch}/rejections',json=payload)
        events=[event for event in self.events(batch) if event['event_type']=='BUYER_REJECTION_RECORDED']
        self.assertEqual(len(events),1)
        self.assertEqual(events[0]['metadata']['reason'],'COSMETIC_DEFECT')

    def test_routing_creation_and_risk_events(self):
        batch=self.batch(risk_level='CRITICAL')
        for _ in range(2):
            self.client.post(f'/produce/{batch}/rerouting')
        types=[event['event_type'] for event in self.events(batch)]
        self.assertEqual(types.count('ROUTING_CASE_CREATED'),1)
        self.assertEqual(types.count('RISK_REVIEWED'),1)

    def test_timeline_read_only_and_unknown_batch(self):
        batch=self.batch()
        before=self.client.get(f'/produce/{batch}').json()
        count=self.count(batch)
        for _ in range(3):
            self.events(batch)
        self.assertEqual(self.count(batch),count)
        self.assertEqual(self.client.get(f'/produce/{batch}').json(),before)
        self.assertEqual(self.client.get('/produce/999999/timeline').status_code,404)

    def test_event_failure_rolls_back_primary_sale(self):
        batch=self.batch()
        before=self.client.get(f'/produce/{batch}').json()
        count=self.count(batch)
        with patch('app.services.transactions.record_event',side_effect=SQLAlchemyError('SECRET')):
            response=self.sell(batch)
            self.assertEqual(response.status_code,500)
            self.assertNotIn('SECRET',response.text)
        self.assertEqual(self.client.get(f'/produce/{batch}').json(),before)
        self.assertEqual(self.count(batch),count)
        self.assertEqual(self.client.get('/transactions').json(),[])

    def test_batch_creation_event_failure_rolls_back(self):
        with patch('app.routes.produce.record_event',side_effect=SQLAlchemyError('SECRET')):
            self.assertEqual(self.client.post('/produce',json=self.produce).status_code,500)
        self.assertEqual(self.client.get('/produce').json(),[])
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(BatchEvent)),0)

    def test_legacy_combined_history_stable_no_invented_events(self):
        timestamp=datetime(2025,1,1,tzinfo=timezone.utc)
        with Session(self.engine) as db:
            batch=ProduceBatch(batch_code='LEGACY',farmer_id=self.farmer['id'],crop_name='Tomato',initial_quantity_kg=Decimal('1000'),sold_quantity_kg=Decimal('100'),remaining_quantity_kg=Decimal('900'),rerouted_quantity_kg=Decimal('0'),expected_price_per_kg=Decimal('25'),harvest_date=date(2025,1,1),quality_grade='A',status='PARTIALLY_SOLD',created_at=timestamp)
            db.add(batch)
            db.flush()
            req=self.client.post('/buyer-requirements',json=self.requirement).json()['id']
            record=Transaction(produce_batch_id=batch.id,buyer_requirement_id=req,buyer_id=self.buyer['id'],quantity_kg=Decimal('100'),transaction_type='PRIMARY_SALE',status='ACCEPTED',created_at=timestamp)
            db.add(record)
            db.commit()
            batch_id=batch.id
        first=self.events(batch_id)
        self.assertEqual(first,self.events(batch_id))
        self.assertEqual(self.count(batch_id),0)
        self.assertEqual([event['event_type'] for event in first],['BATCH_CREATED','PRIMARY_SALE_ACCEPTED'])
        self.assertTrue(all(event['history_origin']=='source_record' for event in first))
        self.assertTrue(all(event['timestamp'].startswith('2025-01-01') for event in first))

    def test_orm_append_only(self):
        batch=self.batch()
        with Session(self.engine) as db:
            record=db.scalar(select(BatchEvent).where(BatchEvent.produce_batch_id==batch))
            record.event_description='Changed'
            with self.assertRaises(ValueError):
                db.flush()
            db.rollback()
            record=db.get(BatchEvent,record.id)
            db.delete(record)
            with self.assertRaises(ValueError):
                db.flush()
            db.rollback()


class ProcessorTraceabilityTests(unittest.TestCase):
    setUp=test_crud.CrudTests.setUp
    tearDown=test_crud.CrudTests.tearDown
    fixture=test_phase10.ProcessorTests.fixture
    accept=test_phase10.ProcessorTests.accept

    def test_processor_events_and_idempotent_retry(self):
        batch,case,req,_=self.fixture()
        self.assertEqual(self.accept(case,req).status_code,200)
        before=self.client.get(f'/produce/{batch}/timeline').json()
        self.accept(case,req)
        self.assertEqual(self.client.get(f'/produce/{batch}/timeline').json(),before)
        types=[event['event_type'] for event in before['events']]
        self.assertEqual(types.count('ALTERNATIVE_ALLOCATION_ACCEPTED'),1)
        self.assertEqual(types.count('BATCH_FULLY_ALLOCATED'),1)
        self.assertEqual(types.count('PROCESSOR_SUITABILITY_RECORDED'),1)
        self.assertNotIn('BATCH_FULLY_UTILIZED',types)

    def test_suitability_repeated_decision_no_duplicate(self):
        batch,case,req,_=self.fixture(assess=False)
        payload={'intended_utilization':'FOOD_PROCESSING','confirmed_condition':'FRESH','suitable':True,'assessed_by':'Test assessor','assessment_notes':'Synthetic assessment'}
        first=self.client.post(f'/routing-cases/{case}/suitability',json=payload).json()
        second=self.client.post(f'/routing-cases/{case}/suitability',json=payload).json()
        self.assertEqual(first,second)
        events=self.client.get(f'/produce/{batch}/timeline').json()['events']
        self.assertEqual(sum(event['event_type']=='PROCESSOR_SUITABILITY_RECORDED' for event in events),1)

    def test_alternative_event_failure_rolls_back(self):
        batch,case,req,_=self.fixture()
        before=self.client.get(f'/produce/{batch}/timeline').json()
        with patch('app.services.alternative_acceptance_service.record_event',side_effect=SQLAlchemyError('SECRET')):
            self.assertEqual(self.accept(case,req).status_code,500)
        self.assertEqual(self.client.get(f'/produce/{batch}/timeline').json(),before)
        self.assertEqual(self.client.get('/alternative-allocations').json(),[])

    def test_legacy_assessment_preserved_when_replaced(self):
        batch,case,req,_=self.fixture(assess=False)
        payload={'intended_utilization':'FOOD_PROCESSING','confirmed_condition':'FRESH','suitable':True,'assessed_by':'Legacy assessor','assessment_notes':'Retained legacy declaration'}
        old=payload|{'crop_name':'Tomato','quality_grade':'A','risk_level':'CRITICAL','assessed_at':datetime.now(timezone.utc).isoformat()}
        with Session(self.engine) as db:
            record=db.get(RoutingCase,case)
            record.trigger_details=record.trigger_details|{'processing_suitability':{'FOOD_PROCESSING':old}}
            db.commit()
        response=self.client.post(f'/routing-cases/{case}/suitability',json=payload|{'assessment_notes':'Updated declaration'})
        self.assertEqual(response.status_code,200,response.text)
        events=self.client.get(f'/produce/{batch}/timeline').json()['events']
        assessments=[event for event in events if event['event_type']=='PROCESSOR_SUITABILITY_RECORDED']
        self.assertEqual(len(assessments),2)
        self.assertEqual({event['metadata']['assessment_notes'] for event in assessments},{'Retained legacy declaration','Updated declaration'})
