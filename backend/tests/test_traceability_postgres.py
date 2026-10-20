import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from fastapi.testclient import TestClient
from sqlalchemy import select,func,text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from app.database import engine
from app.main import app
from app.models import BatchEvent
import test_phase9_postgres


@unittest.skipUnless(os.getenv('AGRIRoute_POSTGRES_TESTS')=='1','Enable isolated PostgreSQL tests')
class TraceabilityPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_phase9_postgres.PostgresConcurrencyTests.setUpClass.__func__(cls)
        # LIKE does not copy triggers. Attach the exact production guard function
        # to the isolated table to test mutation protection without public writes.
        with engine.begin() as connection:
            connection.exec_driver_sql(f'CREATE TRIGGER batch_events_immutable BEFORE UPDATE OR DELETE ON {cls.quoted_schema}.batch_events FOR EACH ROW EXECUTE FUNCTION public.agriroute_batch_events_append_only()')
            connection.exec_driver_sql(f'CREATE TRIGGER batch_events_no_truncate BEFORE TRUNCATE ON {cls.quoted_schema}.batch_events FOR EACH STATEMENT EXECUTE FUNCTION public.agriroute_batch_events_append_only()')

    tearDownClass=classmethod(test_phase9_postgres.PostgresConcurrencyTests.tearDownClass.__func__)
    setUp=test_phase9_postgres.PostgresConcurrencyTests.setUp
    tearDown=test_phase9_postgres.PostgresConcurrencyTests.tearDown

    def test_concurrent_case_events_are_unique(self):
        barrier=Barrier(4)
        def request(_):
            with TestClient(app) as client:
                barrier.wait(timeout=20)
                return client.post(f'/produce/{self.batch_id}/rerouting').status_code
        with ThreadPoolExecutor(max_workers=4) as workers:
            self.assertEqual(list(workers.map(request,range(4))),[200]*4)
        with Session(self.test_engine) as db:
            events=db.scalars(select(BatchEvent).where(BatchEvent.produce_batch_id==self.batch_id)).all()
            self.assertEqual(sorted(event.event_type for event in events),['RISK_REVIEWED','ROUTING_CASE_CREATED'])
            self.assertEqual(len({event.event_key for event in events}),2)

    def test_database_append_only_guards(self):
        with TestClient(app) as client:
            self.assertEqual(client.post(f'/produce/{self.batch_id}/rerouting').status_code,200)
        statements=[f"UPDATE {self.quoted_schema}.batch_events SET event_description='changed' WHERE produce_batch_id=:batch",f'DELETE FROM {self.quoted_schema}.batch_events WHERE produce_batch_id=:batch',f'TRUNCATE {self.quoted_schema}.batch_events']
        for statement in statements:
            with self.assertRaises(DBAPIError):
                with engine.begin() as connection:
                    connection.execute(text(statement),{'batch':self.batch_id})
        with Session(self.test_engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(BatchEvent).where(BatchEvent.produce_batch_id==self.batch_id)),2)
