import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.core.auth import get_current_user, get_identity_db
from auth_support import business_admin


class CrudTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        def test_db():
            with Session(self.engine) as db:
                try:
                    yield db
                except Exception:
                    db.rollback()
                    raise
        app.dependency_overrides[get_db] = test_db
        app.dependency_overrides[get_identity_db] = test_db
        app.dependency_overrides[get_current_user] = business_admin
        self.client = TestClient(app)
        self.code_patch = patch("app.routes.produce.generate_batch_code", return_value="AGR-TOM-0001")
        self.code_patch.start()
        self.farmer = self.client.post("/users", json={"name": "Farmer", "email": "farmer@example.com", "role": "FARMER"}).json()
        self.buyer = self.client.post("/users", json={"name": "Buyer", "email": "buyer@example.com", "role": "BUYER"}).json()
        self.produce = {"farmer_id": self.farmer["id"], "crop_name": "Tomato", "initial_quantity_kg": "1000", "expected_price_per_kg": "25", "harvest_date": "2026-10-05", "quality_grade": "A"}
        self.requirement = {"buyer_id": self.buyer["id"], "crop_name": "Tomato", "required_quantity_kg": "600", "minimum_quality": "A", "minimum_price_per_kg": "20", "maximum_price_per_kg": "25"}

    def tearDown(self):
        self.code_patch.stop()
        self.client.close()
        app.dependency_overrides.clear()
        self.engine.dispose()

    def test_users(self):
        self.assertTrue(self.farmer["is_active"])
        self.assertEqual(self.client.post("/users", json={"name": "Duplicate", "email": "farmer@example.com", "role": "FARMER"}).status_code, 409)
        self.assertEqual(self.client.post("/users", json={"name": "Bad", "email": "bad@example.com", "role": "INVALID"}).status_code, 400)
        self.assertEqual(self.client.get("/users?role=INVALID").status_code, 400)
        self.assertEqual(len(self.client.get("/users?role=FARMER&is_active=true").json()), 1)
        url = f'/users/{self.farmer["id"]}'
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.put(url, json={"name": "Updated", "is_active": False, "latitude": -90, "longitude": 180}).status_code, 200)
        for field in ("email", "role", "id"):
            self.assertEqual(self.client.put(url, json={field: 1}).status_code, 422)
        self.assertEqual(self.client.put(url, json={"name": None}).status_code, 422)
        self.assertEqual(self.client.put(url, json={"latitude": 91}).status_code, 422)
        self.assertEqual(self.client.get("/users/999999").status_code, 404)

    def test_produce(self):
        response = self.client.post("/produce", json=self.produce)
        self.assertEqual(response.status_code, 201, response.text)
        batch = response.json()
        self.assertEqual(batch["remaining_quantity_kg"], "1000.000")
        self.assertEqual(batch["sold_quantity_kg"], "0.000")
        self.assertEqual(batch["rerouted_quantity_kg"], "0.000")
        self.assertEqual(batch["status"], "ACTIVE")
        url = f'/produce/{batch["id"]}'
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(len(self.client.get(f'/produce?farmer_id={self.farmer["id"]}&crop_name=Tomato&status=ACTIVE&risk_level=LOW').json()), 1)
        self.assertEqual(self.client.put(url, json={"expected_price_per_kg": "30", "notes": "Updated"}).status_code, 200)
        for field in ("batch_code", "sold_quantity_kg", "remaining_quantity_kg", "rerouted_quantity_kg", "initial_quantity_kg", "farmer_id", "status", "crop_name"):
            self.assertEqual(self.client.put(url, json={field: 1}).status_code, 422)
        for field in ("batch_code", "sold_quantity_kg", "remaining_quantity_kg", "rerouted_quantity_kg", "status"):
            self.assertEqual(self.client.post("/produce", json=self.produce | {field: 1}).status_code, 422)
        self.assertEqual(self.client.post("/produce", json=self.produce | {"farmer_id": self.buyer["id"]}).status_code, 400)
        self.assertEqual(self.client.post("/produce", json=self.produce | {"farmer_id": 999999}).status_code, 404)
        self.assertEqual(self.client.get("/produce/999999").status_code, 404)
        self.assertEqual(self.client.put(url, json={"expected_price_per_kg": -1}).status_code, 422)

    def test_requirements(self):
        response = self.client.post("/buyer-requirements", json=self.requirement)
        self.assertEqual(response.status_code, 201, response.text)
        requirement = response.json()
        self.assertEqual(requirement["remaining_requirement_kg"], "600.000")
        self.assertEqual(requirement["status"], "OPEN")
        url = f'/buyer-requirements/{requirement["id"]}'
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(len(self.client.get(f'/buyer-requirements?buyer_id={self.buyer["id"]}&crop_name=Tomato&status=OPEN').json()), 1)
        self.assertEqual(self.client.put(url, json={"minimum_price_per_kg": "26"}).status_code, 422)
        self.assertEqual(self.client.put(url, json={"maximum_price_per_kg": "30", "pickup_date": "2026-10-10"}).status_code, 200)
        for field in ("buyer_id", "required_quantity_kg", "remaining_requirement_kg", "status", "crop_name"):
            self.assertEqual(self.client.put(url, json={field: 1}).status_code, 422)
        for field in ("remaining_requirement_kg", "status"):
            self.assertEqual(self.client.post("/buyer-requirements", json=self.requirement | {field: 1}).status_code, 422)
        self.assertEqual(self.client.post("/buyer-requirements", json=self.requirement | {"buyer_id": self.farmer["id"]}).status_code, 400)
        self.assertEqual(self.client.get("/buyer-requirements/999999").status_code, 404)

    def test_safe_database_failure_and_openapi(self):
        with patch("app.routes.users.save", side_effect=OperationalError("SECRET_TEST", {}, Exception("SECRET_TEST"))):
            response = self.client.post("/users", json={"name": "Failure", "email": "failure@example.com", "role": "ADMIN"})
            self.assertEqual(response.status_code, 500)
            self.assertNotIn("SECRET_TEST", response.text)
        self.assertEqual(self.client.get("/health").json(), {"status": "ok", "service": "AgriRoute API"})
        self.assertEqual(self.client.get("/docs").status_code, 200)
        paths = self.client.get("/openapi.json").json()["paths"]
        for prefix in ("/users", "/produce", "/buyer-requirements"):
            self.assertEqual(set(paths[prefix]), {"get", "post"})


if __name__ == "__main__":
    unittest.main()
