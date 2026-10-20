import unittest
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal
from unittest.mock import patch
from sqlalchemy import select, func
from sqlalchemy.orm import Session
import test_crud
from app.models import MatchingAttempt, BuyerRejection, ProduceBatch, BuyerRequirement, Transaction
from app.models.enums import RiskLevel


class TrackingTests(unittest.TestCase):
    setUp = test_crud.CrudTests.setUp
    tearDown = test_crud.CrudTests.tearDown

    def fixtures(self, buyer=True):
        batch = self.client.post('/produce', json=self.produce).json()['id']
        requirement = self.client.post('/buyer-requirements', json=self.requirement).json()['id'] if buyer else None
        return batch, requirement

    def state(self, batch, req=None):
        return (self.client.get(f'/produce/{batch}').json(), self.client.get(f'/buyer-requirements/{req}').json() if req else None, self.client.get('/transactions').json())

    def test_successful_attempt(self):
        batch, req = self.fixtures()
        before = self.state(batch, req)
        result = self.client.post(f'/produce/{batch}/matching-attempts')
        self.assertEqual(result.status_code, 201, result.text)
        self.assertEqual(result.json()['outcome'], 'MATCHES_FOUND')
        self.assertEqual(result.json()['compatible_buyers_found'], 1)
        self.assertEqual(before, self.state(batch, req))

    def test_no_match_and_cooldown(self):
        batch, _ = self.fixtures(False)
        first = self.client.post(f'/produce/{batch}/matching-attempts')
        self.assertEqual(first.json()['outcome'], 'NO_MATCH')
        second = self.client.post(f'/produce/{batch}/matching-attempts')
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()['id'], second.json()['id'])
        self.assertEqual(self.client.get(f'/produce/{batch}/routing-readiness').json()['failed_matching_attempts'], 1)
        with Session(self.engine) as db:
            db.get(MatchingAttempt, first.json()['id']).attempted_at = datetime.now(timezone.utc)-timedelta(seconds=61)
            db.commit()
        self.assertEqual(self.client.post(f'/produce/{batch}/matching-attempts').status_code, 201)

    def test_get_does_not_count(self):
        batch, _ = self.fixtures(False)
        for _ in range(3):
            self.client.get(f'/matches/produce/{batch}')
        self.assertEqual(self.client.get(f'/produce/{batch}/routing-readiness').json()['failed_matching_attempts'], 0)

    def test_empty_history_and_missing_date(self):
        batch, _ = self.fixtures(False)
        output = self.client.get(f'/produce/{batch}/routing-readiness').json()
        self.assertFalse(output['rerouting_candidate'])
        self.assertEqual(output['reasons'], [])
        self.assertTrue(output['warnings'])
        self.assertEqual(output['recommended_action'], 'CONTINUE_PRIMARY_MATCHING')

    def test_valid_rejection_duplicate_no_changes(self):
        batch, req = self.fixtures()
        before = self.state(batch, req)
        payload = {'buyer_requirement_id':req, 'reason':'QUALITY_MISMATCH', 'rejected_quantity_kg':'100', 'notes':'Grade concern'}
        first = self.client.post(f'/produce/{batch}/rejections', json=payload)
        self.assertEqual(first.status_code, 201, first.text)
        duplicate = self.client.post(f'/produce/{batch}/rejections', json=payload | {'rejected_quantity_kg':'100.000'})
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(first.json()['id'], duplicate.json()['id'])
        self.assertEqual(before, self.state(batch, req))
        self.assertEqual(self.client.get(f'/produce/{batch}/routing-readiness').json()['quality_rejections'], 1)

    def test_invalid_rejections(self):
        batch, req = self.fixtures()
        before = self.state(batch, req)
        payload = {'buyer_requirement_id':req, 'reason':'OTHER', 'rejected_quantity_kg':100}
        for changes, status in [({'reason':'INVALID'},422), ({'rejected_quantity_kg':0},422), ({'rejected_quantity_kg':700},409), ({'buyer_requirement_id':999999},404)]:
            self.assertEqual(self.client.post(f'/produce/{batch}/rejections', json=payload | changes).status_code, status)
        self.client.put(f'/users/{self.buyer["id"]}', json={'is_active':False})
        self.assertEqual(self.client.post(f'/produce/{batch}/rejections', json=payload).status_code,400)
        self.assertEqual(before, self.state(batch, req))

    def test_crop_mismatch(self):
        batch, req = self.fixtures()
        with Session(self.engine) as db:
            db.get(BuyerRequirement,req).crop_name='Potato'
            db.commit()
        response=self.client.post(f'/produce/{batch}/rejections',json={'buyer_requirement_id':req,'reason':'OTHER','rejected_quantity_kg':100})
        self.assertEqual(response.status_code,400)

    def test_repeated_failures_recommend_only(self):
        batch, _ = self.fixtures(False)
        before=self.state(batch)
        with Session(self.engine) as db:
            for index in range(3):
                db.add(MatchingAttempt(produce_batch_id=batch,attempted_at=datetime.now(timezone.utc)-timedelta(minutes=index+1),compatible_buyers_found=0,remaining_quantity_at_attempt=Decimal('1000'),outcome='NO_MATCH'))
            db.commit()
        output=self.client.get(f'/produce/{batch}/routing-readiness').json()
        self.assertTrue(output['rerouting_candidate'])
        self.assertEqual(output['recommended_action'],'REVIEW_FOR_ALTERNATIVE_ROUTING')
        self.assertEqual(before,self.state(batch))

    def test_urgency_and_missing_grade(self):
        batch,_=self.fixtures(False)
        with Session(self.engine) as db:
            produce=db.get(ProduceBatch,batch)
            produce.available_until=date.today()
            produce.quality_grade='UNKNOWN'
            db.commit()
        output=self.client.get(f'/produce/{batch}/routing-readiness').json()
        self.assertEqual(output['evaluated_urgency'],'CRITICAL')
        self.assertFalse(output['rerouting_candidate'])
        self.assertEqual(output['recommended_action'],'PRIORITIZE_PRIMARY_SALE')
        self.assertEqual(output['current_risk_level'],'LOW')

    def test_critical_risk(self):
        batch,_=self.fixtures(False)
        self.client.put(f'/produce/{batch}',json={'risk_level':'CRITICAL'})
        self.assertTrue(self.client.get(f'/produce/{batch}/routing-readiness').json()['rerouting_candidate'])

    def test_quality_combination(self):
        batch,req=self.fixtures()
        with Session(self.engine) as db:
            db.add(MatchingAttempt(produce_batch_id=batch,compatible_buyers_found=0,remaining_quantity_at_attempt=Decimal('1000'),outcome='NO_MATCH'))
            db.commit()
        for reason in ('QUALITY_MISMATCH','COSMETIC_DEFECT'):
            self.client.post(f'/produce/{batch}/rejections',json={'buyer_requirement_id':req,'reason':reason,'rejected_quantity_kg':100})
        output=self.client.get(f'/produce/{batch}/routing-readiness').json()
        self.assertTrue(output['rerouting_candidate'])
        self.assertEqual(output['cosmetic_rejections'],1)

    def test_no_inventory(self):
        batch,_=self.fixtures(False)
        with Session(self.engine) as db:
            db.get(ProduceBatch,batch).remaining_quantity_kg=Decimal('0')
            db.commit()
        self.assertEqual(self.client.post(f'/produce/{batch}/matching-attempts').status_code,409)
        self.assertFalse(self.client.get(f'/produce/{batch}/routing-readiness').json()['rerouting_candidate'])

    def test_tracking_rollback(self):
        from sqlalchemy.exc import SQLAlchemyError
        batch,_=self.fixtures(False)
        with patch.object(Session,'refresh',side_effect=SQLAlchemyError('secret')):
            self.assertEqual(self.client.post(f'/produce/{batch}/matching-attempts').status_code,500)
        self.assertEqual(self.client.get(f'/produce/{batch}/routing-readiness').json()['failed_matching_attempts'],0)
