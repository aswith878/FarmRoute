"""Phase 9 functional coverage; every eligible fixture is isolated SQLite data."""
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session
import test_crud
from app.models import ProduceBatch, MatchingAttempt
from app.models.enums import ProduceStatus


class Phase9Tests(unittest.TestCase):
    setUp = test_crud.CrudTests.setUp
    tearDown = test_crud.CrudTests.tearDown

    def batch(self, risk='LOW'):
        return self.client.post('/produce',json=self.produce | {'risk_level':risk}).json()['id']

    def snapshot(self, batch):
        return self.client.get(f'/produce/{batch}').json(), self.client.get('/transactions').json()

    def test_zero_inventory_rejected_without_changes(self):
        batch=self.batch('CRITICAL')
        with Session(self.engine) as db:
            db.get(ProduceBatch,batch).remaining_quantity_kg=Decimal('0')
            db.commit()
        before=self.snapshot(batch)
        self.assertEqual(self.client.post(f'/produce/{batch}/rerouting').status_code,409)
        self.assertEqual(self.snapshot(batch),before)
        self.assertEqual(self.client.get('/routing-cases').json(),[])

    def test_cancelled_and_completed_produce(self):
        batch=self.batch('CRITICAL')
        for status in (ProduceStatus.CANCELLED,ProduceStatus.COMPLETED):
            with Session(self.engine) as db:
                db.get(ProduceBatch,batch).status=status
                db.commit()
            before=self.snapshot(batch)
            self.assertEqual(self.client.post(f'/produce/{batch}/rerouting').status_code,409)
            self.assertEqual(self.snapshot(batch),before)
        self.assertEqual(self.client.get('/routing-cases').json(),[])

    def test_low_risk_one_failure_not_eligible(self):
        batch=self.batch()
        with Session(self.engine) as db:
            db.add(MatchingAttempt(produce_batch_id=batch,compatible_buyers_found=0,remaining_quantity_at_attempt=Decimal('1000'),outcome='NO_MATCH'))
            db.commit()
        before=self.snapshot(batch)
        self.assertEqual(self.client.post(f'/produce/{batch}/rerouting').status_code,409)
        self.assertEqual(self.snapshot(batch),before)

    def test_threshold_reasons_and_snapshot_fields(self):
        batch=self.batch()
        with Session(self.engine) as db:
            for index in range(3):
                db.add(MatchingAttempt(produce_batch_id=batch,attempted_at=datetime.now(timezone.utc)-timedelta(minutes=index+1),compatible_buyers_found=0,remaining_quantity_at_attempt=Decimal('1000'),outcome='NO_MATCH'))
            db.commit()
        expected=self.client.get(f'/produce/{batch}/routing-readiness').json()
        before=self.snapshot(batch)
        response=self.client.post(f'/produce/{batch}/rerouting')
        self.assertEqual(response.status_code,200,response.text)
        case=response.json()
        self.assertEqual(case['trigger_reason'],'ROUTING_READINESS_ELIGIBLE')
        self.assertEqual(case['trigger_details']['reasons'],expected['reasons'])
        self.assertIn('3 genuine NO_MATCH attempts reached the review threshold.',case['trigger_details']['reasons'])
        self.assertEqual(case['trigger_details']['failed_matching_attempts'],3)
        self.assertEqual(case['quantity_kg'],'1000.000')
        self.assertEqual(case['risk_level_at_creation'],'LOW')
        self.assertEqual(case['status'],'AWAITING_ALTERNATIVE_MATCH')
        self.assertEqual(self.client.get(f'/routing-cases/{case["id"]}').json(),case)
        self.assertEqual(self.client.get('/routing-cases').json(),[case])
        self.assertEqual(self.snapshot(batch),before)

    def test_no_processor_transactions_even_with_processor_present(self):
        processor=self.client.post('/users',json={'name':'Processor','email':'processor@example.com','role':'PROCESSOR'}).json()
        self.assertEqual(processor['role'],'PROCESSOR')
        batch=self.batch('CRITICAL')
        before=self.snapshot(batch)
        self.assertEqual(self.client.post(f'/produce/{batch}/rerouting').status_code,200)
        self.assertEqual(self.snapshot(batch),before)
        self.assertEqual(self.client.get('/transactions').json(),[])
