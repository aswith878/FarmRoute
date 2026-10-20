"""Create the requested demo records through HTTP; reuse records on reruns."""
import json
import sys
from decimal import Decimal
from urllib.parse import urlencode
from urllib.request import Request, urlopen

base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"


def api(path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    request = Request(base_url.rstrip("/") + path, data=data, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def demo_user(name, email, role):
    existing = next((user for user in api("/users") if user["email"] == email), None)
    if existing:
        if existing["role"] != role:
            raise RuntimeError("Existing demo email has an unexpected role.")
        return existing
    return api("/users", {"name": name, "email": email, "role": role, "location_name": "Puducherry"})


def main():
    farmer = demo_user("Arun Kumar", "arun.farmer@agriroute.demo", "FARMER")
    buyer = demo_user("FreshMart Wholesale", "freshmart@agriroute.demo", "BUYER")
    processor = demo_user("South Foods Processing", "southfoods@agriroute.demo", "PROCESSOR")
    batches = api("/produce?" + urlencode({"farmer_id": farmer["id"], "crop_name": "Tomato"}))
    batch = next((record for record in batches if record["initial_quantity_kg"] == "1000.000" and record["harvest_date"] == "2026-10-05"), None)
    if batch is None:
        batch = api("/produce", {"farmer_id": farmer["id"], "crop_name": "Tomato", "initial_quantity_kg": "1000", "expected_price_per_kg": "25", "harvest_date": "2026-10-05", "quality_grade": "A", "risk_level": "LOW", "location_name": "Puducherry"})
    requirements = api("/buyer-requirements?" + urlencode({"buyer_id": buyer["id"], "crop_name": "Tomato"}))
    requirement = next((record for record in requirements if record["required_quantity_kg"] == "600.000" and record["minimum_quality"] == "A"), None)
    if requirement is None:
        requirement = api("/buyer-requirements", {"buyer_id": buyer["id"], "crop_name": "Tomato", "required_quantity_kg": "600", "minimum_quality": "A", "minimum_price_per_kg": "20", "maximum_price_per_kg": "25", "location_name": "Puducherry"})
    # Re-read each record to verify committed state through GET endpoints.
    batch = api(f'/produce/{batch["id"]}')
    requirement = api(f'/buyer-requirements/{requirement["id"]}')
    # Reruns must preserve legitimate sales recorded after the initial seeding.
    assert sum(Decimal(batch[field]) for field in ("sold_quantity_kg", "remaining_quantity_kg", "rerouted_quantity_kg")) == Decimal("1000")
    assert Decimal("0") <= Decimal(requirement["remaining_requirement_kg"]) <= Decimal("600")
    print(json.dumps({"farmer_id": farmer["id"], "buyer_id": buyer["id"], "processor_id": processor["id"], "produce": batch, "buyer_requirement": requirement}, indent=2))


if __name__ == "__main__":
    main()
