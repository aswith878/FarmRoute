# Risk and rejection tracking (Phase 8)

No existing sale, matching, or frontend logic is changed. There is no automatic
transaction, routing decision, processor matching, or food-safety/AI prediction.

## Migration and startup

From `C:\FarmRoute\backend`:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Revision `9144c60ea9dd_add_matching_attempts_and_buyer_.py` creates only
`matching_attempts` and `buyer_rejections`, their indexes, checks, and foreign
keys. Existing tables are preserved. Inspect the public schema in Supabase Table
Editor and filter tracking records by produce_batch_id.

## Explicit tracking endpoints

- POST `/produce/{batch_id}/matching-attempts`: locks the batch, verifies remaining
  primary inventory, runs the existing matching service, and records PRIMARY,
  compatible buyer count, quantity snapshot, timestamp, and MATCHES_FOUND/NO_MATCH.
  Returns 201 for a new record. Within cooldown, returns the previous record with
  HTTP 200 without recalculating or incrementing counts. This is an explicit POST;
  GET `/matches/produce/{batch_id}` never creates attempts. The batch lock serializes
  concurrent POSTs and also cooperates with acceptance locks.
- POST `/produce/{batch_id}/rejections`: accepts buyer_requirement_id, reason,
  rejected_quantity_kg, and optional notes. Reasons are QUALITY_MISMATCH,
  COSMETIC_DEFECT, PRICE_DISAGREEMENT, PICKUP_UNAVAILABLE, QUANTITY_MISMATCH, OTHER.
  Requires active BUYER, OPEN/PARTIALLY_FILLED requirement, exact case-insensitive
  crop compatibility, and positive quantity within both available balances.
  Locks batch then requirement. No transaction or quantity changes are made.
  Identical batch/requirement/reason/normalized quantity/trimmed notes are protected
  by a SHA-256 fingerprint and a database unique constraint. Replays return the
  existing record with HTTP 200; new records return 201. Identical feedback is
  deduplicated permanently; it is not counted as a new rejection event. Existing
  records may be replayed even if the buyer requirement subsequently changes;
  new records always validate its current eligibility. Blank/null notes normalize
  to the same fingerprint. Notes are limited to 4000 characters.
- GET `/produce/{batch_id}/routing-readiness`: calculates current counts and rules
  from the database. No writes occur. Unknown batch returns 404; tracking POSTs
  without available primary inventory return 409. Validation uses clean 400/422
  responses and safe generic database error handling.

## Configurable prototype thresholds

Set these positive integers in backend/.env or environment and restart the server:

| Setting | Default |
| --- | ---: |
| MATCHING_ATTEMPT_COOLDOWN_SECONDS | 60 |
| ROUTING_FAILED_ATTEMPT_THRESHOLD | 3 |
| ROUTING_QUALITY_REJECTION_THRESHOLD | 2 |
| ROUTING_URGENT_DEADLINE_DAYS | 1 |
| ROUTING_COMBINED_FAILURE_THRESHOLD | 2 |

Counts use all persisted history for this batch: genuine NO_MATCH attempt records
and unique rejection records. Successful attempts are recorded separately and do
not count as failures. There is no background retry scheduler or automatic reset.

With remaining primary inventory, alternative-routing **review** is recommended if:

1. Existing risk is CRITICAL; or
2. Failed attempts reach 3; or
3. At least 2 failures combine with HIGH/CRITICAL risk, a deadline within 1 day,
   or existing grade C; or
4. At least 1 failure combines with at least 2 QUALITY_MISMATCH/COSMETIC_DEFECT
   rejection records.

These thresholds use the configuration above. Candidate false otherwise. Zero
inventory or completed/cancelled/rerouting status never activates a candidate.
One NO_MATCH alone is insufficient.

Evaluated urgency starts from the existing risk. A deadline within 1 day raises it
to HIGH; due/past deadlines raise it to CRITICAL. This is logistical urgency only,
not a claim about spoilage, edibility, or food safety. Missing deadlines/unknown
grades generate warnings; they are not invented. Buyer feedback does not change
the stored grade or risk, and cosmetic feedback is never treated as food-safety evidence.

Recommended action is REVIEW_FOR_ALTERNATIVE_ROUTING for a candidate, otherwise
PRIORITIZE_PRIMARY_SALE for non-LOW urgency or quality/cosmetic feedback, otherwise
CONTINUE_PRIMARY_MATCHING. `current_risk_level` always reflects stored risk;
`evaluated_urgency` is a separate read-only assessment. Reasons explain observed
indicators and triggered review conditions. No status or quantity is updated.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Rejection and elevated urgency scenarios run in isolated SQLite fixtures. The
live demo only records an explicit NO_MATCH for batch 1, verifies cooldown reuse,
and reads readiness, preserving 150 kg Remaining Inventory and existing risk/grade.

Verified live result: matching attempt ID 1, PRIMARY, 0 compatible buyers,
NO_MATCH, quantity snapshot 150.000. An immediate repeat reused ID 1. Readiness
reported LOW stored risk and evaluated urgency, 1 failed attempt, 0 quality and
cosmetic rejections, candidate false, reasons [], and CONTINUE_PRIMARY_MATCHING.
The missing availability date was returned as a warning. Both tracking tables
are present in Supabase, migration is at head, and all 52 automated tests passed.
Existing quantities, status, quality, risk, transactions, health, and docs were preserved.
