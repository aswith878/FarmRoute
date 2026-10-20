import unittest
from decimal import Decimal
from unittest.mock import patch
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import test_crud
from app.models import ProduceBatch,RoutingCase,ProcessorRequirement
from app.models.routing_case import RoutingCaseStatus


class ProcessorTests(unittest.TestCase):
    setUp=test_crud.CrudTests.setUp
    tearDown=test_crud.CrudTests.tearDown

    def fixture(self,quantity='150',assess=True,**changes):
        batch=self.client.post('/produce',json=self.produce|{'initial_quantity_kg':'150','risk_level':'CRITICAL','visible_condition':'FRESH'}).json()['id']
        case=self.client.post(f'/produce/{batch}/rerouting').json()['id']
        processor=self.client.post('/users',json={'name':'Processor','email':'processor@phase10.demo','role':'PROCESSOR'}).json()['id']
        payload={'processor_id':processor,'crop_name':'tomato','required_quantity_kg':quantity,'minimum_acceptable_quality':'A','acceptable_produce_conditions':['FRESH'],'intended_utilization':'FOOD_PROCESSING','minimum_price_per_kg':'10','maximum_price_per_kg':'30'}|changes
        response=self.client.post('/processor-requirements',json=payload)
        self.assertEqual(response.status_code,201,response.text)
        req=response.json()['id']
        if assess:
            result=self.client.post(f'/routing-cases/{case}/suitability',json={'intended_utilization':'FOOD_PROCESSING','confirmed_condition':'FRESH','suitable':True,'assessed_by':'Isolated test assessor','assessment_notes':'Synthetic fixture declaration, not actual food safety evidence.'})
            self.assertEqual(result.status_code,200,result.text)
        return batch,case,req,processor

    def accept(self,case,req,qty='150',key='test-key',**extra):
        return self.client.post(f'/routing-cases/{case}/accept',json={'processor_requirement_id':req,'accepted_quantity_kg':qty,'price_per_kg':'25'}|extra,headers={'Idempotency-Key':key})

    def inventory(self,batch):
        return self.client.get(f'/produce/{batch}').json()

    def test_eligible_matching_read_only(self):
        batch,case,req,_=self.fixture(quantity='100')
        before=self.inventory(batch)
        response=self.client.get(f'/routing-cases/{case}/processor-matches')
        self.assertEqual(response.status_code,200,response.text)
        match=response.json()['matches'][0]
        self.assertEqual(match['processor_requirement_id'],req)
        self.assertEqual(match['compatible_quantity_kg'],'100.000')
        self.assertEqual(match['intended_utilization'],'FOOD_PROCESSING')
        self.assertIn('Explicit assessment',match['suitability_explanation'])
        self.assertEqual(self.inventory(batch),before)
        self.assertEqual(self.client.get('/alternative-allocations').json(),[])

    def test_crop_mismatch(self):
        _,case,_,_=self.fixture(crop_name='Potato')
        self.assertEqual(self.client.get(f'/routing-cases/{case}/processor-matches').json()['matches'],[])

    def test_quality_mismatch(self):
        batch,case,req,_=self.fixture()
        self.client.put(f'/produce/{batch}',json={'quality_grade':'B'})
        self.assertEqual(self.client.get(f'/routing-cases/{case}/processor-matches').json()['matches'],[])
        self.assertEqual(self.accept(case,req).status_code,409)

    def test_quality_compatible(self):
        _,case,_,_=self.fixture(minimum_acceptable_quality='B')
        self.assertEqual(len(self.client.get(f'/routing-cases/{case}/processor-matches').json()['matches']),1)

    def test_missing_suitability(self):
        batch,case,req,_=self.fixture(assess=False)
        before=self.inventory(batch)
        response=self.client.get(f'/routing-cases/{case}/processor-matches').json()
        self.assertEqual(response['matches'],[])
        self.assertTrue(response['warnings'])
        self.assertEqual(self.accept(case,req).status_code,409)
        self.assertEqual(self.inventory(batch),before)

    def test_partial_acceptance(self):
        batch,case,req,_=self.fixture()
        response=self.accept(case,req,'50')
        self.assertEqual(response.status_code,200,response.text)
        state=self.inventory(batch)
        self.assertEqual(state['remaining_quantity_kg'],'100.000')
        self.assertEqual(state['rerouted_quantity_kg'],'50.000')
        self.assertEqual(state['sold_quantity_kg'],'0.000')
        self.assertEqual(self.client.get(f'/routing-cases/{case}').json()['status'],'MATCHED')
        self.assertEqual(self.client.get(f'/processor-requirements/{req}').json()['status'],'PARTIALLY_FILLED')
        self.assertEqual(self.client.get(f'/routing-cases/{case}/processor-matches').json()['available_quantity_kg'],'100.000')

    def test_complete_acceptance_and_conservation(self):
        batch,case,req,_=self.fixture()
        response=self.accept(case,req)
        self.assertEqual(response.status_code,200,response.text)
        state=self.inventory(batch)
        self.assertEqual(state['remaining_quantity_kg'],'0.000')
        self.assertEqual(state['rerouted_quantity_kg'],'150.000')
        self.assertEqual(state['status'],'COMPLETED')
        self.assertEqual(Decimal(state['initial_quantity_kg']),sum(Decimal(state[key]) for key in ('sold_quantity_kg','remaining_quantity_kg','rerouted_quantity_kg')))
        self.assertEqual(self.client.get(f'/routing-cases/{case}').json()['status'],'COMPLETED')
        self.assertEqual(self.client.get(f'/processor-requirements/{req}').json()['status'],'FULFILLED')
        self.assertEqual(response.json()['status'],'ACCEPTED_ALLOCATED')

    def test_requirement_exhaustion(self):
        batch,case,req,_=self.fixture(quantity='50')
        self.assertEqual(self.accept(case,req,'50').status_code,200)
        self.assertEqual(self.accept(case,req,'1','different-key').status_code,409)
        self.assertEqual(self.inventory(batch)['remaining_quantity_kg'],'100.000')

    def test_duplicate_and_key_conflict(self):
        batch,case,req,_=self.fixture()
        first=self.accept(case,req)
        self.assertEqual(first.status_code,200,first.text)
        before=self.inventory(batch)
        retry=self.accept(case,req)
        self.assertEqual(retry.json(),first.json())
        self.assertEqual(self.accept(case,req,'10').status_code,409)
        self.assertEqual(self.inventory(batch),before)
        self.assertEqual(len(self.client.get('/alternative-allocations').json()),1)

    def test_invalid_quantities(self):
        batch,case,req,_=self.fixture()
        before=self.inventory(batch)
        for qty,status in [('0',422),('-1',422),('151',409),('0.0001',422)]:
            self.assertEqual(self.accept(case,req,qty).status_code,status)
        self.assertEqual(self.inventory(batch),before)

    def test_missing_idempotency_key(self):
        _,case,req,_=self.fixture()
        self.assertEqual(self.client.post(f'/routing-cases/{case}/accept',json={'processor_requirement_id':req,'accepted_quantity_kg':'10'}).status_code,422)

    def test_ineligible_case(self):
        batch,case,req,_=self.fixture()
        with Session(self.engine) as db:
            db.get(RoutingCase,case).status=RoutingCaseStatus.CANCELLED
            db.commit()
        before=self.inventory(batch)
        self.assertEqual(self.accept(case,req).status_code,409)
        self.assertEqual(self.inventory(batch),before)

    def test_stale_case_revalidates_inventory(self):
        batch,case,req,_=self.fixture()
        # A real primary acceptance changes inventory after case creation.
        buyer_req=self.client.post('/buyer-requirements',json=self.requirement|{'required_quantity_kg':'100'}).json()['id']
        result=self.client.post('/transactions/accept',json={'produce_batch_id':batch,'buyer_requirement_id':buyer_req,'quantity_kg':'100'})
        self.assertEqual(result.status_code,201,result.text)
        self.assertEqual(self.accept(case,req,'150').status_code,409)
        self.assertEqual(self.accept(case,req,'50').status_code,200)
        state=self.inventory(batch)
        self.assertEqual(state['sold_quantity_kg'],'100.000')
        self.assertEqual(state['rerouted_quantity_kg'],'50.000')
        self.assertEqual(state['remaining_quantity_kg'],'0.000')

    def test_case_quantity_cap(self):
        batch,case,req,_=self.fixture()
        with Session(self.engine) as db:
            db.get(RoutingCase,case).quantity_kg=Decimal('25')
            db.commit()
        self.assertEqual(self.accept(case,req,'26').status_code,409)
        self.assertEqual(self.accept(case,req,'25').status_code,200)
        self.assertEqual(self.inventory(batch)['remaining_quantity_kg'],'125.000')
        self.assertEqual(self.client.get(f'/routing-cases/{case}').json()['status'],'COMPLETED')

    def test_rollback(self):
        batch,case,req,_=self.fixture()
        before=self.inventory(batch)
        with patch.object(Session,'refresh',side_effect=SQLAlchemyError('SECRET')):
            response=self.accept(case,req)
            self.assertEqual(response.status_code,500)
            self.assertNotIn('SECRET',response.text)
        self.assertEqual(self.inventory(batch),before)
        self.assertEqual(self.client.get('/alternative-allocations').json(),[])
        self.assertEqual(self.client.get(f'/processor-requirements/{req}').json()['remaining_requirement_kg'],'150.000')
        self.assertEqual(self.client.get(f'/routing-cases/{case}').json()['status'],'AWAITING_ALTERNATIVE_MATCH')

    def test_primary_transactions_unchanged(self):
        _,case,req,_=self.fixture()
        before=self.client.get('/transactions').json()
        self.accept(case,req)
        self.assertEqual(self.client.get('/transactions').json(),before)

    def test_active_processor_validation(self):
        _,_,_,processor=self.fixture()
        self.client.put(f'/users/{processor}',json={'is_active':False})
        self.assertEqual(self.client.post('/processor-requirements',json={'processor_id':processor,'crop_name':'Tomato','required_quantity_kg':'1','minimum_acceptable_quality':'A','acceptable_produce_conditions':['FRESH'],'intended_utilization':'FOOD_PROCESSING','minimum_price_per_kg':'10','maximum_price_per_kg':'30'}).status_code,400)
