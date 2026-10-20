"""Run the authorized Buyer B demo using existing HTTP endpoints."""
import json
import sys
from urllib.request import Request, urlopen

base = (sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8000').rstrip('/')


def api(path, payload=None):
    req = Request(base+path, data=json.dumps(payload).encode() if payload is not None else None, headers={'Content-Type':'application/json'})
    with urlopen(req, timeout=30) as response:
        return json.load(response)


def main():
    buyer = next((user for user in api('/users') if user['email'] == 'greenbasket@agriroute.demo'), None)
    if buyer is None:
        buyer = api('/users', {'name':'Green Basket Retail', 'email':'greenbasket@agriroute.demo', 'role':'BUYER', 'location_name':'Puducherry', 'latitude':'11.9416', 'longitude':'79.8083'})
    requirement = next((row for row in api(f'/buyer-requirements?buyer_id={buyer["id"]}&crop_name=Tomato') if row['required_quantity_kg'] == '250.000'), None)
    if requirement is None:
        requirement = api('/buyer-requirements', {'buyer_id':buyer['id'], 'crop_name':'Tomato', 'required_quantity_kg':'250', 'minimum_quality':'A', 'minimum_price_per_kg':'20', 'maximum_price_per_kg':'30', 'maximum_distance_km':'50', 'pickup_date':'2026-10-06', 'location_name':'Puducherry', 'latitude':'11.9416', 'longitude':'79.8083'})
    transactions = api(f'/transactions?produce_batch_id=1&buyer_id={buyer["id"]}')
    existing = next((row for row in transactions if row['buyer_requirement_id'] == requirement['id'] and row['quantity_kg'] == '250.000'), None)
    before = api('/matches/produce/1')
    if existing is None:
        assert before['remaining_quantity_kg'] == '400.000'
        match = next(row for row in before['matches'] if row['buyer_requirement_id'] == requirement['id'])
        assert match['matchable_quantity_kg'] == '250.000'
        transaction = api('/transactions/accept', {'produce_batch_id':1, 'buyer_requirement_id':requirement['id'], 'quantity_kg':'250', 'price_per_kg':'25'})
    else:
        transaction = existing
    produce = api('/produce/1')
    requirement = api(f'/buyer-requirements/{requirement["id"]}')
    after = api('/matches/produce/1')
    assert produce['sold_quantity_kg'] == '850.000' and produce['remaining_quantity_kg'] == '150.000'
    assert produce['rerouted_quantity_kg'] == '0.000' and produce['status'] == 'PARTIALLY_SOLD'
    assert requirement['remaining_requirement_kg'] == '0.000' and requirement['status'] == 'FULFILLED'
    print(json.dumps({'buyer_b_id':buyer['id'], 'requirement_id':requirement['id'], 'match_before_sale':before, 'transaction':transaction, 'produce_after':produce, 'requirement_after':requirement, 'remaining_inventory_matches':after}, indent=2))


if __name__ == '__main__':
    main()
