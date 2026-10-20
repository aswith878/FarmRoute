import unittest
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import test_crud
from app.services.matching_service import score_requirement, haversine_km


class ScoreTests(unittest.TestCase):
    def setUp(self):
        self.today = date(2026, 10, 6)
        self.batch = SimpleNamespace(crop_name='Tomato', quality_grade='A', remaining_quantity_kg=Decimal('400'), expected_price_per_kg=Decimal('25'), latitude=None, longitude=None, harvest_date=self.today, available_until=self.today+timedelta(days=5), risk_level='LOW')
        self.requirement = SimpleNamespace(id=2, crop_name='Tomato', minimum_quality='A', remaining_requirement_kg=Decimal('250'), minimum_price_per_kg=Decimal('20'), maximum_price_per_kg=Decimal('30'), latitude=None, longitude=None, maximum_distance_km=Decimal('50'), pickup_date=self.today)
        self.buyer = SimpleNamespace(id=4, name='Buyer')

    def score(self):
        return score_requirement(self.batch, self.requirement, self.buyer, self.today)

    def test_exact_crop(self):
        self.assertIsNotNone(self.score())

    def test_case_insensitive_crop(self):
        self.requirement.crop_name = 'tomato'
        self.assertIsNotNone(self.score())

    def test_crop_mismatch(self):
        self.requirement.crop_name = 'Potato'
        self.assertIsNone(self.score())

    def test_partial_quantity(self):
        self.assertEqual(self.score()['matchable_quantity_kg'], Decimal('250'))

    def test_larger_buyer_quantity(self):
        self.requirement.remaining_requirement_kg = Decimal('600')
        self.assertEqual(self.score()['matchable_quantity_kg'], Decimal('400'))

    def test_quality_compatible(self):
        self.requirement.minimum_quality = 'B'
        self.assertEqual(self.score()['score_breakdown']['quality'], 100)

    def test_quality_incompatible(self):
        self.batch.quality_grade = 'B'
        self.assertIsNone(self.score())

    def test_missing_quality(self):
        self.batch.quality_grade = None
        self.assertEqual(self.score()['score_breakdown']['quality'], 50)
        self.assertTrue(self.score()['warnings'])

    def test_price_compatibility(self):
        self.assertEqual(self.score()['score_breakdown']['price'], 100)
        self.batch.expected_price_per_kg = Decimal('32')
        self.assertLess(self.score()['score_breakdown']['price'], 100)
        self.batch.expected_price_per_kg = Decimal('40')
        self.assertIsNone(self.score())

    def test_missing_price(self):
        self.batch.expected_price_per_kg = None
        self.assertEqual(self.score()['score_breakdown']['price'], 50)

    def test_distance(self):
        self.assertAlmostEqual(haversine_km(0, 0, 0, 1), 111.195, places=3)
        self.batch.latitude = self.batch.longitude = 0
        self.requirement.latitude, self.requirement.longitude = 0, 1
        self.assertIsNone(self.score())
        self.requirement.maximum_distance_km = Decimal('200')
        self.assertAlmostEqual(self.score()['distance_km'], 111.195, places=3)

    def test_missing_coordinates(self):
        self.assertIsNone(self.score()['distance_km'])
        self.assertEqual(self.score()['score_breakdown']['distance'], 50)

    def test_pickup_dates(self):
        self.requirement.pickup_date = self.today+timedelta(days=6)
        self.assertIsNone(self.score())
        self.requirement.pickup_date = None
        self.assertEqual(self.score()['score_breakdown']['pickup'], 50)

    def test_urgency(self):
        self.batch.risk_level = 'CRITICAL'
        fast = self.score()['score_breakdown']['urgency']
        self.requirement.pickup_date = self.today+timedelta(days=4)
        self.assertLess(self.score()['score_breakdown']['urgency'], fast)


class MatchingApiTests(unittest.TestCase):
    setUp = test_crud.CrudTests.setUp
    tearDown = test_crud.CrudTests.tearDown

    def fixtures(self):
        batch = self.client.post('/produce', json=self.produce).json()
        requirement = self.client.post('/buyer-requirements', json=self.requirement).json()
        return batch['id'], requirement['id']

    def matches(self, batch_id):
        response = self.client.get(f'/matches/produce/{batch_id}')
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()['matches']

    def test_fulfilled_excluded(self):
        batch, req = self.fixtures()
        from app.models import BuyerRequirement
        from app.models.enums import RequirementStatus
        from sqlalchemy.orm import Session
        with Session(self.engine) as db:
            db.get(BuyerRequirement, req).status = RequirementStatus.FULFILLED
            db.commit()
        self.assertEqual(self.matches(batch), [])

    def test_cancelled_excluded(self):
        batch, req = self.fixtures()
        from app.models import BuyerRequirement
        from app.models.enums import RequirementStatus
        from sqlalchemy.orm import Session
        with Session(self.engine) as db:
            db.get(BuyerRequirement, req).status = RequirementStatus.CANCELLED
            db.commit()
        self.assertEqual(self.matches(batch), [])

    def test_inactive_buyer_excluded(self):
        batch, _ = self.fixtures()
        self.client.put(f'/users/{self.buyer["id"]}', json={'is_active': False})
        self.assertEqual(self.matches(batch), [])

    def test_wrong_role_excluded(self):
        batch, req = self.fixtures()
        from app.models import BuyerRequirement
        from sqlalchemy.orm import Session
        with Session(self.engine) as db:
            db.get(BuyerRequirement, req).buyer_id = self.farmer['id']
            db.commit()
        self.assertEqual(self.matches(batch), [])

    def test_ranking(self):
        batch, _ = self.fixtures()
        self.client.post('/buyer-requirements', json=self.requirement | {'required_quantity_kg':'1000'})
        matches = self.matches(batch)
        self.assertEqual(len(matches), 2)
        self.assertGreater(matches[0]['match_score'], matches[1]['match_score'])

    def test_zero_remaining(self):
        batch, _ = self.fixtures()
        from app.models import ProduceBatch
        from sqlalchemy.orm import Session
        with Session(self.engine) as db:
            db.get(ProduceBatch, batch).remaining_quantity_kg = Decimal('0')
            db.commit()
        self.assertEqual(self.matches(batch), [])

    def test_no_matches_and_missing_batch(self):
        batch = self.client.post('/produce', json=self.produce).json()['id']
        self.assertEqual(self.matches(batch), [])
        self.assertEqual(self.client.get('/matches/produce/999999').status_code, 404)

    def test_read_only(self):
        batch, req = self.fixtures()
        before = self.client.get(f'/produce/{batch}').json()
        self.matches(batch)
        self.assertEqual(self.client.get(f'/produce/{batch}').json(), before)
