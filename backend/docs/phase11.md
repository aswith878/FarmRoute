# Phase 11: batch traceability and lifecycle history

## Storage and append-only rules

Migration `3530a8eba68f_add_append_only_batch_events.py` adds only `batch_events`,
its foreign key to produce_batches, indexes on batch/type/time, and a unique
event_key. JSONB metadata is mapped to `event_metadata` in Python because SQLAlchemy
reserves `metadata`. Quantities remain Numeric(14,3)/Decimal; timestamps are timezone-aware.
Related source type/ID references identify transactions, attempts, rejections,
cases, or alternative allocations without changing their schemas.

Events are append-only. PostgreSQL triggers reject UPDATE, DELETE, and TRUNCATE;
ORM listeners reject ordinary model edits/deletes. There is no client mutation
API. Schema migrations and privileged DDL remain administrative operations.

## Recorded actions

- BATCH_CREATED: completed produce creation.
- PRIMARY_MATCH_ATTEMPTED: explicit matching POST, excluding cooldown reuse.
- PRIMARY_SALE_ACCEPTED: committed primary quantity acceptance.
- BUYER_REJECTION_RECORDED: unique rejection, not duplicate replay.
- RISK_REVIEWED: readiness snapshot when an eligible new routing case is initiated.
- ROUTING_CASE_CREATED: new case, excluding active-case reuse.
- PROCESSOR_SUITABILITY_RECORDED: a new/changed explicit suitability decision.
  Identical declaration retries preserve the assessment timestamp and record no event.
- ALTERNATIVE_ALLOCATION_ACCEPTED: new allocated quantity, excluding idempotent retry.
- BATCH_FULLY_ALLOCATED: the operation that reduces remaining inventory to zero.

Existing arithmetic and row locks are preserved. `record_event` does not commit;
it flushes within the business operation's transaction. Event persistence failure
rolls back the corresponding sale, case, attempt, rejection, or allocation. Event
keys include action/source ID; suitability keys include utilization and stored
assessment time. Unique keys plus existing batch locks prevent duplicate events.
GET requests never add events. No inventory is changed by the timeline service.

## Legacy history: combined projections, no synthetic backfill writes

GET timeline merges append-only events with legacy projections from actual
produce_batches, transactions, matching_attempts, buyer_rejections, routing_cases,
and alternative_allocations. Projections use stored source IDs and timestamps.
Recorded events supersede matching projection keys, producing one logical event.
Repeated reads are stable and do not create rows. No backfill job is required.

Legacy suitability is available only if the case's stored JSON contains an actual
assessed_at value. Only retained historical declarations can be shown; overwritten
pre-Phase-11 assessments cannot be reconstructed. Invalid/missing historical
assessment dates are omitted instead of invented. Legacy previous/new statuses
are null because the old records do not retain those transition snapshots.
When a retained legacy declaration is replaced after Phase 11, it is first
preserved as an append-only event with its actual timestamp in the same transaction.

For a zero-remaining legacy batch, a fully allocated milestone is shown only when
all accepted primary and alternative source quantities sum exactly to the initial
quantity. Its evidence references the latest stored allocation timestamp/source.
It is explicitly a derived allocation milestone, not a physical-utilization event.
For newly tracked batches the actual stored milestone supersedes that derivation.
Historical event IDs are `historical:<action>:<source>:<id>` (plus assessment suffix);
recorded events use their integer batch_events IDs. `history_origin` distinguishes them.

## Timeline API

GET `/produce/{batch_id}/timeline`, Swagger tag Batch Traceability. Missing batch
returns 404. A shared PostgreSQL batch lock keeps the inventory/source snapshot
consistent with concurrent acceptance operations. Event ordering uses UTC timestamp
then stable action/source key. This deterministic tie-breaker makes no claim about
sub-second causality when legacy timestamps are equal.

Example:

```json
{
  "batch_id": 1,
  "batch_code": "AGR-TOM-0001",
  "crop_name": "Tomato",
  "initial_quantity_kg": "1000.000",
  "sold_quantity_kg": "850.000",
  "remaining_quantity_kg": "150.000",
  "rerouted_quantity_kg": "0.000",
  "events": [{
    "event_id": "historical:PRIMARY_SALE_ACCEPTED:transaction:1",
    "event_type": "PRIMARY_SALE_ACCEPTED",
    "description": "Primary sale accepted; physical delivery is not confirmed.",
    "quantity_kg": "600.000",
    "timestamp": "<actual stored timestamp>",
    "related_entity": {"type": "transaction", "id": 1},
    "metadata": {"buyer_id": 2},
    "previous_status": null,
    "new_status": null,
    "history_origin": "source_record"
  }]
}
```

The example timestamp is intentionally a placeholder; the real API returns the
record's stored ISO timestamp, not an invented date. Decimal API values are strings.

Allocation/acceptance is distinct from delivery, consumption, actual utilization,
or measured waste prevention. There is no BATCH_FULLY_UTILIZED event. These future
physical confirmations are outside Phase 11.

## Verification

```powershell
cd C:\FarmRoute\backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic check
$env:AGRIRoute_POSTGRES_TESTS='1'
$env:AGRIRoute_LIVE_VERIFY='1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Read `/produce/1/timeline` and `/produce/2/timeline`. Supabase public.batch_events
stores new actions; legacy projections are API-only and deliberately do not appear
as fabricated backfilled rows in Table Editor. No existing inventory, quality,
risk, routing case, or acceptance record is rewritten to construct history.
No React, authentication, AI, or Phase 12 work is included.

## Verified results — 6 October 2026

- Supabase revision `3530a8eba68f` is applied; Alembic reports no pending differences.
  batch_events JSONB, the three required indexes, unique event keys, and append-only
  guards were verified. PostgreSQL tests rejected UPDATE, DELETE, and TRUNCATE.
- All 109 tests passed, including all previous 92, event/operation rollback,
  duplicate retries, legacy history retention, and concurrent event creation.
- Batch 1 has four source-backed events: creation, transaction 1 accepting 600 kg,
  transaction 2 accepting 250 kg, and matching attempt 1 (NO_MATCH). Its inventory
  remains 1000/850/150/0 kg and status PARTIALLY_SOLD; no processor acceptance exists.
- Batch 2 has seven source-backed events: creation, transaction 3 accepting 850 kg,
  risk review/case 1 initiation, stored suitability assessment, allocation 1 accepting
  150 kg, and BATCH_FULLY_ALLOCATED. Quantities remain 1000/850/0/150 kg, COMPLETED.
- Repeated timeline reads returned the same ordering/IDs and created no event rows.
  Original quantities, statuses, and updated_at timestamps were unchanged.
- Health, database health, Swagger registration, and frontend Git diff were checked.
  No React changes, fabricated utilization confirmations, or unexpected errors.
  The existing TestClient deprecation warning is non-failing; generic database-error
  logs are expected output from rollback tests.
