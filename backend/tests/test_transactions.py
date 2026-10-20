import unittest
from unittest.mock import patch
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.dialects import postgresql

from app.models import ProduceBatch, BuyerRequirement, Transaction
from app.models.enums import ProduceStatus, RequirementStatus
import test_crud


class TransactionTests(unittest.TestCase):
    setUp = test_crud.CrudTests.setUp
    tearDown = test_crud.CrudTests.tearDown

    def fixtures(self, quantity="1000", requirement_quantity="600", crop="tomato"):
        batch = self.client.post('/produce', json=self.produce | {'initial_quantity_kg': quantity}).json()
        requirement = self.client.post('/buyer-requirements', json=self.requirement | {'required_quantity_kg': requirement_quantity, 'crop_name': crop}).json()
        return {'produce_batch_id': batch['id'], 'buyer_requirement_id': requirement['id'], 'quantity_kg': '600', 'price_per_kg': '25'}

    def snapshot(self):
        with Session(self.engine) as db:
            batch = db.scalar(select(ProduceBatch))
            requirement = db.scalar(select(BuyerRequirement))
            return (batch.sold_quantity_kg, batch.remaining_quantity_kg, batch.rerouted_quantity_kg, batch.status, requirement.remaining_requirement_kg, requirement.status, db.scalar(select(func.count()).select_from(Transaction)))

    def reject_unchanged(self, payload, status):
        before = self.snapshot()
        response = self.client.post('/transactions/accept', json=payload)
        self.assertEqual(response.status_code, status, response.text)
        self.assertEqual(self.snapshot(), before)

    def test_full_buyer_fulfilment(self):
        payload = self.fixtures()
        response = self.client.post('/transactions/accept', json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        record = response.json()
        self.assertEqual(record['buyer_id'], self.buyer['id'])
        self.assertEqual(record['transaction_type'], 'PRIMARY_SALE')
        self.assertEqual(record['status'], 'ACCEPTED')
        self.assertEqual(self.snapshot(), (Decimal('600'), Decimal('400'), Decimal('0'), ProduceStatus.PARTIALLY_SOLD, Decimal('0'), RequirementStatus.FULFILLED, 1))
        self.assertEqual(self.client.get(f'/transactions/{record["id"]}').status_code, 200)
        self.assertEqual(len(self.client.get(f'/transactions?produce_batch_id={payload["produce_batch_id"]}&buyer_id={self.buyer["id"]}').json()), 1)
        self.assertEqual(self.client.get('/transactions/999999').status_code, 404)
        self.reject_unchanged(payload | {'quantity_kg': '1'}, 409)

    def test_partial_fulfilment(self):
        payload = self.fixtures()
        response = self.client.post('/transactions/accept', json=payload | {'quantity_kg': '100.125', 'price_per_kg': None})
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(self.snapshot(), (Decimal('100.125'), Decimal('899.875'), Decimal('0'), ProduceStatus.PARTIALLY_SOLD, Decimal('499.875'), RequirementStatus.PARTIALLY_FILLED, 1))
        self.assertIsNone(response.json()['price_per_kg'])

    def test_produce_completion(self):
        payload = self.fixtures(quantity='600')
        self.assertEqual(self.client.post('/transactions/accept', json=payload).status_code, 201)
        self.assertEqual(self.snapshot()[1], Decimal('0'))
        self.assertEqual(self.snapshot()[3], ProduceStatus.COMPLETED)

    def test_insufficient_produce(self):
        self.reject_unchanged(self.fixtures(quantity='500'), 409)

    def test_requirement_exceeded(self):
        self.reject_unchanged(self.fixtures() | {'quantity_kg': '700'}, 409)

    def test_zero_negative_and_controlled_fields(self):
        payload = self.fixtures()
        for quantity in ('0', '-1', '0.0001'):
            self.reject_unchanged(payload | {'quantity_kg': quantity}, 422)
        for name in ('buyer_id', 'transaction_type', 'status'):
            self.reject_unchanged(payload | {name: 1}, 422)
        self.reject_unchanged(payload | {'price_per_kg': '-1'}, 422)

    def test_crop_mismatch(self):
        self.reject_unchanged(self.fixtures(crop='Potato'), 400)

    def test_missing_records_and_invalid_buyer(self):
        payload = self.fixtures()
        self.reject_unchanged(payload | {'produce_batch_id': 999999}, 404)
        self.reject_unchanged(payload | {'buyer_requirement_id': 999999}, 404)
        with Session(self.engine) as db:
            db.get(BuyerRequirement, payload['buyer_requirement_id']).buyer_id = self.farmer['id']
            db.commit()
        self.reject_unchanged(payload, 400)

    def test_blocked_statuses(self):
        payload = self.fixtures()
        for status in (ProduceStatus.CANCELLED, ProduceStatus.COMPLETED, ProduceStatus.REROUTING):
            with Session(self.engine) as db:
                db.get(ProduceBatch, payload['produce_batch_id']).status = status
                db.commit()
            self.reject_unchanged(payload, 409)
        with Session(self.engine) as db:
            db.get(ProduceBatch, payload['produce_batch_id']).status = ProduceStatus.ACTIVE
            db.get(BuyerRequirement, payload['buyer_requirement_id']).status = RequirementStatus.CANCELLED
            db.commit()
        self.reject_unchanged(payload, 409)

    def test_rollback_after_quantity_updates_and_insert(self):
        payload = self.fixtures()
        # refresh runs after flush has issued INSERT and quantity UPDATEs.
        with patch.object(Session, 'refresh', side_effect=SQLAlchemyError('SECRET_TEST')):
            self.reject_unchanged(payload, 500)
        self.assertEqual(self.client.post('/transactions/accept', json=payload).status_code, 201)

    def test_lock_queries_use_postgres_for_update(self):
        for model in (ProduceBatch, BuyerRequirement):
            query = select(model).where(model.id == 1).with_for_update()
            self.assertIn('FOR UPDATE', str(query.compile(dialect=postgresql.dialect())))


if __name__ == '__main__':
    unittest.main()
