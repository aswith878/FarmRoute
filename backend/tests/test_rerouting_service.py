import unittest
from decimal import Decimal
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

import test_crud
from app.models import ProduceBatch, RoutingCase
from app.models.routing_case import RoutingCaseStatus
from app.services.rerouting_service import request_rerouting


class ReroutingServiceTests(unittest.TestCase):
    setUp = test_crud.CrudTests.setUp
    tearDown = test_crud.CrudTests.tearDown

    def batch(self, eligible=True):
        return self.client.post('/produce', json=self.produce | {'risk_level': 'CRITICAL' if eligible else 'LOW'}).json()['id']

    def request(self, batch_id):
        with Session(self.engine) as db:
            return request_rerouting(db, batch_id)

    def case_count(self):
        with Session(self.engine) as db:
            return db.scalar(select(func.count()).select_from(RoutingCase))

    def test_eligible_case_and_unchanged_inventory(self):
        batch = self.batch()
        before = self.client.get(f'/produce/{batch}').json()
        transactions = self.client.get('/transactions').json()
        case = self.request(batch)
        self.assertEqual(case.quantity_kg, Decimal('1000.000'))
        self.assertEqual(case.status, RoutingCaseStatus.AWAITING_ALTERNATIVE_MATCH)
        self.assertEqual(case.risk_level_at_creation.value, 'CRITICAL')
        self.assertTrue(case.trigger_details['rerouting_candidate'])
        self.assertTrue(case.trigger_details['reasons'])
        self.assertEqual(case.trigger_details['remaining_quantity_kg'], '1000.000')
        self.assertEqual(self.client.get(f'/produce/{batch}').json(), before)
        self.assertEqual(self.client.get('/transactions').json(), transactions)

    def test_active_case_reused(self):
        batch = self.batch()
        first = self.request(batch)
        second = self.request(batch)
        self.assertEqual(first.id, second.id)
        self.assertEqual(self.case_count(), 1)
        with Session(self.engine) as db:
            db.get(RoutingCase, first.id).status = RoutingCaseStatus.MATCHED
            db.commit()
        self.assertEqual(self.request(batch).id, first.id)

    def test_terminal_case_allows_new_case(self):
        batch = self.batch()
        first = self.request(batch)
        with Session(self.engine) as db:
            db.get(RoutingCase, first.id).status = RoutingCaseStatus.CANCELLED
            db.commit()
        self.assertNotEqual(self.request(batch).id, first.id)
        self.assertEqual(self.case_count(), 2)

    def test_ineligible_and_missing_batch(self):
        batch = self.batch(False)
        for batch_id, status in ((batch,409),(999999,404)):
            with self.assertRaises(HTTPException) as result:
                self.request(batch_id)
            self.assertEqual(result.exception.status_code,status)
        self.assertEqual(self.case_count(),0)

    def test_no_remaining_quantity(self):
        batch = self.batch()
        with Session(self.engine) as db:
            db.get(ProduceBatch,batch).remaining_quantity_kg=Decimal('0')
            db.commit()
        with self.assertRaises(HTTPException) as result:
            self.request(batch)
        self.assertEqual(result.exception.status_code,409)
        self.assertEqual(self.case_count(),0)

    def test_readiness_recalculated_on_retry(self):
        batch = self.batch()
        self.request(batch)
        self.client.put(f'/produce/{batch}',json={'risk_level':'LOW'})
        with self.assertRaises(HTTPException):
            self.request(batch)
        self.assertEqual(self.case_count(),1)

    def test_creation_failure_rolls_back(self):
        batch = self.batch()
        before=self.client.get(f'/produce/{batch}').json()
        with patch.object(Session,'refresh',side_effect=SQLAlchemyError('secret')):
            with self.assertRaises(SQLAlchemyError):
                self.request(batch)
        self.assertEqual(self.case_count(),0)
        self.assertEqual(self.client.get(f'/produce/{batch}').json(),before)
