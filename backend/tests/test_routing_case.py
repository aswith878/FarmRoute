import unittest
from decimal import Decimal
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable
import test_crud
from app.models import RoutingCase
from app.models.routing_case import RoutingCaseStatus


class RoutingCaseTests(unittest.TestCase):
    setUp = test_crud.CrudTests.setUp
    tearDown = test_crud.CrudTests.tearDown

    def case(self, batch, **changes):
        values = dict(produce_batch_id=batch, quantity_kg=Decimal('150.125'), trigger_reason='MANUAL_REVIEW', trigger_details={'failed_attempts': 3}, risk_level_at_creation='LOW')
        return RoutingCase(**(values | changes))

    def test_duplicate_active_case_and_terminal_history(self):
        batch = self.client.post('/produce', json=self.produce).json()['id']
        with Session(self.engine) as db:
            first = self.case(batch)
            db.add(first)
            db.commit()
            first_id = first.id
            self.assertEqual(first.status, RoutingCaseStatus.AWAITING_ALTERNATIVE_MATCH)
            self.assertEqual(first.quantity_kg, Decimal('150.125'))
            self.assertEqual(first.trigger_details, {'failed_attempts':3})
            db.add(self.case(batch, status=RoutingCaseStatus.MATCHED))
            with self.assertRaises(IntegrityError):
                db.commit()
            db.rollback()
            db.get(RoutingCase, first_id).status = RoutingCaseStatus.COMPLETED
            db.commit()
            second = self.case(batch, status=RoutingCaseStatus.MATCHED)
            db.add(second)
            db.commit()
            db.add(self.case(batch))
            with self.assertRaises(IntegrityError):
                db.commit()
            db.rollback()
            second.status = RoutingCaseStatus.CANCELLED
            db.commit()
            db.add(self.case(batch))
            db.commit()

    def test_positive_quantity(self):
        batch = self.client.post('/produce', json=self.produce).json()['id']
        for quantity in (Decimal('0'), Decimal('-1')):
            with Session(self.engine) as db:
                db.add(self.case(batch, quantity_kg=quantity))
                with self.assertRaises(IntegrityError):
                    db.commit()

    def test_postgres_jsonb(self):
        sql = str(CreateTable(RoutingCase.__table__).compile(dialect=postgresql.dialect()))
        self.assertIn('trigger_details JSONB', sql)
