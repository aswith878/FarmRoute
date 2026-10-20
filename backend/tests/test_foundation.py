import unittest
from datetime import date
from decimal import Decimal

from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, configure_mappers

from app.database import Base
from app.models import BuyerRequirement, ProduceBatch, User
from app.schemas import BuyerRequirementCreate, BuyerRequirementRead, ProduceBatchCreate, ProduceBatchRead, UserCreate, UserRead


class FoundationTests(unittest.TestCase):
    def setUp(self):
        self.produce = dict(farmer_id=1, crop_name="Tomato", initial_quantity_kg="100.125", expected_price_per_kg="20.50", harvest_date=date.today(), quality_grade="A")
        self.requirement = dict(buyer_id=2, crop_name="Tomato", required_quantity_kg="80.125", minimum_quality="A", minimum_price_per_kg="10.00", maximum_price_per_kg="25.00")

    def test_validation_and_server_controlled_fields(self):
        for field in ("sold_quantity_kg", "remaining_quantity_kg", "rerouted_quantity_kg"):
            with self.assertRaises(ValidationError):
                ProduceBatchCreate(**self.produce, **{field: 1})
        with self.assertRaises(ValidationError):
            BuyerRequirementCreate(**self.requirement, remaining_requirement_kg=1)
        for schema, payload, changes in (
            (ProduceBatchCreate, self.produce, {"initial_quantity_kg": 0}),
            (ProduceBatchCreate, self.produce, {"expected_price_per_kg": -1}),
            (BuyerRequirementCreate, self.requirement, {"required_quantity_kg": 0}),
            (BuyerRequirementCreate, self.requirement, {"minimum_price_per_kg": -1}),
            (BuyerRequirementCreate, self.requirement, {"maximum_price_per_kg": -1}),
            (BuyerRequirementCreate, self.requirement, {"maximum_price_per_kg": 1}),
            (ProduceBatchCreate, self.produce, {"latitude": 91}),
            (BuyerRequirementCreate, self.requirement, {"longitude": -181}),
            (ProduceBatchCreate, self.produce, {"risk_level": "INVALID"}),
        ):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                schema(**(payload | changes))
        UserCreate(name="Farmer", email="farmer@example.com", role="FARMER", latitude=-90, longitude=180)

    def test_defaults_relationships_and_read_schemas(self):
        configure_mappers()
        self.assertEqual(set(Base.metadata.tables), {"users", "produce_batches", "buyer_requirements", "transactions", "matching_attempts", "buyer_rejections", "routing_cases", "processor_requirements", "alternative_allocations", "batch_events"})
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)  # Isolated test DB only; never Supabase.
        with Session(engine) as session:
            farmer = User(name="Farmer", email="farmer@example.com", role="FARMER")
            buyer = User(name="Buyer", email="buyer@example.com", role="BUYER")
            session.add_all([farmer, buyer])
            session.flush()
            produce = ProduceBatch(batch_code="TEST", **ProduceBatchCreate(**(self.produce | {"farmer_id": farmer.id})).model_dump())
            requirement = BuyerRequirement(**BuyerRequirementCreate(**(self.requirement | {"buyer_id": buyer.id})).model_dump())
            session.add_all([produce, requirement])
            session.flush()
            self.assertEqual(produce.remaining_quantity_kg, Decimal("100.125"))
            self.assertEqual(produce.sold_quantity_kg, Decimal("0"))
            self.assertEqual(produce.rerouted_quantity_kg, Decimal("0"))
            self.assertEqual(requirement.remaining_requirement_kg, Decimal("80.125"))
            self.assertIs(produce.farmer, farmer)
            self.assertIs(requirement.buyer, buyer)
            self.assertIn(produce, farmer.produce_batches)
            self.assertIn(requirement, buyer.buyer_requirements)
            self.assertTrue(UserRead.model_validate(farmer).is_active)
            ProduceBatchRead.model_validate(produce)
            BuyerRequirementRead.model_validate(requirement)
        engine.dispose()


if __name__ == "__main__":
    unittest.main()
