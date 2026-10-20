# Phase 10: processor matching and allocated quantities

The additive migration `3db7d033e01c_add_processor_requirements_and_.py` adds
`processor_requirements` and `alternative_allocations`. Primary transactions and
BUYER-only requirements are unchanged. Existing tables/constraints are preserved.

## API

- POST/GET `/processor-requirements`, GET `/processor-requirements/{requirement_id}`.
  Create validates active PROCESSOR, Decimal quantities/prices, and coordinates;
  remaining quantity and OPEN status are assigned by the server.
- POST `/routing-cases/{case_id}/suitability`: explicit human assessment for a
  named intended utilization. Requires confirmed_condition matching the recorded
  visible condition, suitable boolean, assessed_by, and assessment_notes. Stores
  the declaration with condition/crop/grade/risk snapshots inside existing JSONB
  trigger details. No quantities move and no transaction is created. Unsuitable or
  missing assessments exclude the destination. Changes to the recorded condition,
  grade, crop, or risk require a new assessment. This declaration is not an AI
  quality prediction, actual safety certification, or proof of physical utilization.
- GET `/routing-cases/{case_id}/processor-matches`: ranked recommendations for an
  active case. Missing suitability yields an empty array and human-review warning.
- POST `/routing-cases/{case_id}/accept`: body processor_requirement_id,
  accepted_quantity_kg, optional price_per_kg. Requires `Idempotency-Key` header
  (1–128 characters; not blank). Returns the allocated record with HTTP 200.
- GET `/alternative-allocations` (optional routing_case_id),
  GET `/alternative-allocations/{allocation_id}` return committed allocation records.

## Transparent scoring

| Factor | Weight |
| --- | ---: |
| Crop | 10% |
| Quantity | 15% |
| Quality | 10% |
| Recorded condition | 10% |
| Explicit processing suitability | 20% |
| Price | 10% |
| Distance | 10% |
| Pickup | 10% |
| Urgency | 5% |

Constants live in `processor_matching_service.py`. Quality must be known A/B/C
and satisfy the requested minimum. Recorded condition must exactly match a
declared acceptable condition after trimming/case normalization. Positive human
suitability for the exact utilization and unchanged snapshots is mandatory,
including food processing and animal feed. Rejections/urgency never prove safety.
Other scores reuse the documented primary scoring primitives: exact case-insensitive
crop, min available quantity, price range/deviation, Haversine distance, pickup
window, and urgency. Unknown coordinates return null distance with neutral score.
Matching and ranking never change quantities, case status, or allocation records.

## Atomicity, idempotency, and stale cases

Lock order: produce batch, routing case, processor requirement. Primary acceptance
uses the same first batch lock. Under PostgreSQL READ COMMITTED, each overlapping
request rechecks committed remaining inventory after acquiring the lock.

Available case quantity = max(0, min(current batch remaining, original case quantity
minus accepted alternative allocations)). Primary sales can shrink availability;
requests exceeding it return 409 and make no changes. A stale zero-inventory case
returns no matches and rejects new acceptance; it is not automatically modified.

Each acceptance atomically inserts one alternative allocation, decreases remaining
batch/processor quantities, and increases only rerouted quantity. Primary sold
quantity never changes. Inventory conservation is checked before writes and is
preserved by equal remaining decrease/rerouted increase. Agreed price, if supplied,
must fall inside the processor range. New incompatible acceptance returns 409;
missing entities return 404; invalid numeric/extra fields return 422.

Retries with the same key and equivalent payload return the same allocation,
even after completion. A different payload with the same key returns 409. The
case lock and unique (case,key) database constraint prevent duplicate allocation.
Clients must keep a stable key when retrying uncertain responses; a new key means
a new requested allocation. All write/refresh/serialization failures roll back.

Case stays MATCHED after partial allocation and becomes COMPLETED when its current
available quantity is fully allocated. Batch becomes COMPLETED only if remaining
inventory reaches zero; otherwise its prior status stays unchanged. Requirement
becomes PARTIALLY_FILLED/FULFILLED. ACCEPTED_ALLOCATED does **not** mean physically
delivered, consumed, utilized, or measured waste prevented. There is no delivery
confirmation workflow in this phase.

## Run and verify

```powershell
cd C:\FarmRoute\backend
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
$env:AGRIRoute_POSTGRES_TESTS='1'
$env:AGRIRoute_LIVE_VERIFY='1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

In another terminal run ` .\.venv\Scripts\python.exe scripts\demo_phase10.py`.
This creates a distinct synthetic demo batch and dedicated users, accepts 850 kg
through the existing primary API, records a suitability declaration, then allocates
150 kg to a processor. Live batch 1 remains unchanged at 1000/850/150/0 kg and
is not forced eligible. Inspect printed IDs in Supabase Table Editor's public
schema. All demo records are synthetic, not real suitability or food-safety evidence.

No frontend, authentication, AI/ML, physical-utilization claims, or Phase 11 changes.

## Verified results — 6 October 2026

All 92 automated tests passed, including the previous 72 and real PostgreSQL
processor concurrency, duplicate-key retries, and primary-versus-alternative races.
Temporary schemas were removed. The initial PostgreSQL fixture bulk-enum casting
error was corrected by inserting synthetic users individually; final runs passed.
The existing TestClient dependency deprecation warning is non-failing.

Supabase is at revision `3db7d033e01c`, with no pending schema differences. Demo:

- Dedicated batch 2, AGR-TOM-0002; farmer 5, primary buyer 6, processor 7.
- Processor requirement 1, 150.000 kg, FOOD_PROCESSING, declared acceptable FRESH
  condition, minimum B, price 15–30, pickup 2026-10-06. Synthetic assessment only.
- Routing case 1, AWAITING_ALTERNATIVE_MATCH before acceptance, COMPLETED afterward.
- Match: 150.000 kg, distance 0.421 km, score 99.95; no inventory change on matching.
- Alternative allocation 1: processor 7, requirement 1, batch 2, case 1,
  150.000 kg at 20.00, ACCEPTED_ALLOCATED. Requirement is FULFILLED with zero remaining.
- Before alternative acceptance: 1000.000 initial, 850.000 primary sold,
  150.000 remaining, 0.000 rerouted. After: 1000.000 / 850.000 / 0.000 / 150.000.
- Live batch 1 remains 1000.000 / 850.000 / 150.000 / 0.000 with LOW risk and
  readiness false; rerouting still returns 409. No quality/risk changes were made.
- Supabase records, health endpoints, Swagger, and cleanup were independently
  checked. No primary model/service or React source changes were made.
