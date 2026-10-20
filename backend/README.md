# AgriRoute API

Phase 12 implements FastAPI JWT authentication, Argon2id password hashing,
role-based access control and record ownership checks. React and business quantity
calculations remain unchanged. See [Phase 12 architecture, permissions, activation,
security limitations, and files changed](docs/phase12.md).

Verified: **149 tests passed**, including all **109 previous business tests**,
real JWT role/ownership tests, and isolated Supabase concurrency checks. Migration
`e9e552718ba4` is applied; Alembic check reports no pending schema differences.
All existing rows across 10 application tables match their pre-migration digests.
Seven legacy users retain NULL credentials and must be explicitly activated.
Batch 1 remains initial/sold/remaining/rerouted **1000/850/150/0 kg** with LOW risk
and one failed attempt; rerouting remains 409. Batch 2 remains 1000/850/0/150 kg.
Timeline counts remain four and seven. No live user, transaction, allocation,
quantity or history source was rewritten.

Public auth endpoints: POST `/auth/register` and POST `/auth/login`.
GET `/auth/me` and all business endpoints require a bearer access token.
Health and documentation endpoints remain public. `/docs` advertises HTTP bearer
Authorize on protected operations. Real HTTP health/docs checks passed, and
unauthenticated protected requests return 401. Real JWT login/profile and
concurrent registration were verified in isolated Supabase schemas, then cleaned up.

From `C:\FarmRoute\backend`, restart with:

```powershell
.\.venv-local\Scripts\python.exe -m pip install -r requirements.txt
.\.venv-local\Scripts\python.exe -m alembic upgrade head
.\.venv-local\Scripts\python.exe -m uvicorn app.main:app --reload
```

Configure `DATABASE_URL`, `JWT_SECRET` and `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` in
private `backend/.env`; see `.env.example`. The local JWT secret was securely
randomly generated and is not committed. No default password was assigned.
Activate an existing active demo account through a non-echoing local prompt:

```powershell
.\.venv-local\Scripts\python.exe -m scripts.activate_user 1
```

A trusted local operator can bootstrap a new administrator explicitly with
`python -m scripts.create_admin`; no administrator was automatically created.

Phase 15 adds optional farmer photo uploads through authenticated FastAPI to
the `agriroute-produce-images` Supabase Storage bucket. Migration
`9c71d435bc02` provisions the bucket. Configure `SUPABASE_URL` and
`SUPABASE_SERVICE_ROLE_KEY` in private `backend/.env` before enabling uploads;
keep the service key on the server and never expose it to Vite/browser code.
Install updated packages from `requirements.txt` for multipart upload support.
See the repository's [Phase 15 storage notes](../docs/phase15.md).

Phase 16 adds administrator account search, role/status filters, and guarded
activation/deactivation. The API blocks self-deactivation and protects the
last active administrator. See [Phase 16 account access](../docs/phase16.md).
For this checkout, use the working `backend/.venv-local` Python environment.

Swagger: http://127.0.0.1:8000/docs. Health: http://127.0.0.1:8000/health.
Database health: http://127.0.0.1:8000/health/db. In Swagger, log in, click Authorize
and paste access_token. The verification server used port 8001 and was stopped
after checks; run the startup command to start your development server.

Production requires the shared gateway/Redis rate-limiting strategy documented
in phase12.md. Refresh tokens, remote password reset, MFA and token revocation
are not implemented. No unexpected errors remain; failure tests intentionally
produce sanitized error logs, and the existing TestClient/httpx deprecation
warning is non-failing. The frontend integration work is recorded in Phases
13–16; the detailed phase notes describe remaining live-configuration work.

---

## Earlier phase records

The following sections are historical verification snapshots; Phase 12 above
is the current state. Earlier examples require the appropriate bearer token.

# AgriRoute API foundation

Phase 11 adds append-only batch events and GET `/produce/{batch_id}/timeline`.
See [Phase 11 event types, transaction safety, legacy history, and verification](docs/phase11.md).
Migration `3530a8eba68f` adds JSONB events with PostgreSQL mutation guards. Existing
records are represented through a deduplicated read-only combined timeline;
no inventory rewrite or fabricated backfill is performed.

Phase 11 verification: 109 tests passed (including the previous 92), migration
`3530a8eba68f` is applied in Supabase, and health/Swagger pass. Batch 1 timeline
shows four recorded-source actions; batch 2 shows seven including its actual
stored suitability declaration and full-allocation milestone. Both inventories
and statuses remain unchanged. See phase11.md for legacy event IDs and limitations.

Phase 10 adds processor requirements, explicit suitability assessments, processor
recommendations, and atomic alternative allocations. See [Phase 10 API, scoring,
inventory, idempotency, tests, and demo instructions](docs/phase10.md). Historical
Phase 9 verification below records the earlier stage; current migration includes
the additive Phase 10 tables.

Verified Phase 10: revision `3db7d033e01c`, 92 tests passing. Dedicated synthetic
batch 2 (AGR-TOM-0002) allocated 150 kg to processor 7 via requirement 1, case 1,
allocation 1. Its final quantities are initial 1000, primary sold 850, remaining 0,
rerouted 150 kg. Live batch 1 remains 1000/850/150/0 kg and ineligible for rerouting.
Allocation confirms acceptance only, not physical delivery/utilization.

## Final Phase 9 verification — 6 October 2026

- All 72 automated tests passed with PostgreSQL concurrency and live verification
  enabled; all 52 earlier tests remain passing. Eligible scenarios use isolated data.
- Supabase `alembic_version` is `8ec5cbd75d95` (head); Alembic check reports no new
  upgrade operations. `public.routing_cases` exists with the active-case unique
  index. Four concurrent requests returned one case; duplicate requests reused it.
- Real HTTP checks passed for `/health`, `/health/db`, `/docs`, and OpenAPI registration
  of POST `/produce/{batch_id}/rerouting`, GET `/routing-cases`, and
  GET `/routing-cases/{case_id}`. Case detail/list responses passed isolated API tests.
- Live batch 1 remains initial 1000.000, sold 850.000, remaining 150.000, rerouted
  0.000 kg. Risk is LOW, failed attempts 1. POST rerouting returned 409, created no
  case, and preserved all inventory and existing transactions. Readiness is false,
  reasons [], action CONTINUE_PRIMARY_MATCHING; missing deadline is a warning.
- Temporary PostgreSQL test schemas were removed. No processor transactions,
  automatic routing, frontend integration, or Phase 10 functionality was added.
- Frontend file hashes were checked before/after verification; React remains unchanged.
  This verification modifies only this README, not application or test code.
- No unexpected failures occurred. The test runner emits a third-party TestClient
  deprecation warning; generic database-error logs are expected rollback-test output.

## Phase 9 test verification

Comprehensive coverage includes eligible/ineligible requests, duplicates, real
PostgreSQL concurrent requests, zero inventory, cancelled/completed produce,
inventory preservation, exact trigger reasons, case GET endpoints, and absence
of processor transactions. The full enabled suite passed 72 tests, including all
52 Phase 8 tests and subsequent routing model/service/API tests.

Run the isolated functional suite:

```powershell
cd C:\FarmRoute\backend
.\.venv-local\Scripts\python.exe -m unittest discover -s tests -v
```

Enable the actual PostgreSQL concurrency and live verification checks:

```powershell
$env:AGRIRoute_POSTGRES_TESTS = '1'
$env:AGRIRoute_LIVE_VERIFY = '1'
.\.venv-local\Scripts\python.exe -m unittest discover -s tests -v
Remove-Item Env:AGRIRoute_POSTGRES_TESTS
Remove-Item Env:AGRIRoute_LIVE_VERIFY
```

PostgreSQL tests require the configured database user to create/drop an isolated
schema. A UUID-named `agriroute_phase9_test_*` schema copies table definitions with
independent identity sequences; no public row or sequence is modified. Four
concurrent HTTP requests use separate database sessions and produce one active
case. The temporary schema is removed after the test. Native PostgreSQL enums
are referenced, not recreated. Without flags, these two integration tests skip;
70 functional/regression tests still run without live writes.

The live verification checks batch 1 remains LOW risk with 150.000 kg and one
failed attempt, confirms POST rerouting returns 409, and compares before/after
inventory, cases, transactions, and readiness. It never changes risk/quality or
creates eligible live demo data. If those expected demo preconditions change,
the test fails rather than modifying the demo to fit the assertion. All eligible
test scenarios use isolated SQLite or temporary PostgreSQL data.

`app/services/rerouting_service.py` exposes `request_rerouting(db, batch_id)`.
Supply a fresh SQLAlchemy session; the service owns its atomic transaction, locks
the produce row, recalculates Phase 8 readiness, and rejects ineligible inventory
with 409 (missing batch: 404). Eligible retries reuse an active case; otherwise it
creates an AWAITING_ALTERNATIVE_MATCH case with the current remaining quantity,
risk, readiness reasons, and rule thresholds. The returned ORM case is a detached
snapshot usable after session close. Creation does not reserve, sell, reroute, or
change produce status or quantities. No processor matching is added.

Routing API (Swagger tag: Routing Cases):

- POST `/produce/{batch_id}/rerouting`: 200 with a new or existing active case;
  409 when readiness is false or inventory unavailable; 404 for a missing batch.
  Readiness is recalculated before active-case reuse, as required by the service.
- GET `/routing-cases`: all cases ordered by ID, including terminal history.
- GET `/routing-cases/{case_id}`: full details, or 404 when absent.

Responses include quantity, trigger reason and JSON details (including readiness
reasons), risk at creation, status, batch ID, and timestamps. Existing endpoints
and frontend integration remain unchanged. View them at http://localhost:8000/docs.

Routing-case storage is available through the SQLAlchemy `RoutingCase` model and
Alembic revision `8ec5cbd75d95_add_routing_cases.py`. Quantities are Numeric(14,3)
Decimal and trigger details are PostgreSQL JSONB. All four statuses are supported:
AWAITING_ALTERNATIVE_MATCH (default), MATCHED, COMPLETED, CANCELLED. A partial unique
index permits at most one AWAITING_ALTERNATIVE_MATCH/MATCHED case per batch, even
under concurrent inserts; completed/cancelled history is retained. The migration
reuses the existing risk enum and changes no existing tables. No routing-case API,
automatic case creation, inventory changes, or processor matching is added.
Apply with `.\.venv-local\Scripts\python.exe -m alembic upgrade head` from backend.

Phase 8 adds explicit matching attempts, buyer rejections, and read-only routing
readiness. See [risk tracking rules and endpoints](docs/risk-tracking.md).

An independent FastAPI backend using PostgreSQL and SQLAlchemy. The existing
React frontend is unchanged and is not connected to this API. Database models
and Pydantic schemas, basic CRUD, and primary buyer recommendations are implemented;
authentication, AI/ML,
and rerouting are intentionally not implemented. Manual primary-sale acceptance
and transaction recording are implemented.

## Setup (Windows PowerShell)

Use Python 3.10 or newer and an installed, running PostgreSQL server.
Use your existing Supabase Session Pooler URL, or create a local PostgreSQL
database named `agriroute` and a user with access to it.

From the project root:

```powershell
cd backend
python -m venv .venv-local
.\.venv-local\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `backend/.env` and replace the placeholders with your PostgreSQL credentials:

```dotenv
DATABASE_URL=postgresql://username:password@localhost:5432/agriroute
```

URL-encode special characters in the username/password. Do not commit `.env`.
Existing environment variables take precedence over values in `.env`.

If virtual environment activation is unavailable, use
`.\.venv-local\Scripts\python.exe -m pip install -r requirements.txt` and
`.\.venv-local\Scripts\python.exe -m uvicorn app.main:app --reload` directly.

For macOS/Linux, activate with `source .venv-local/bin/activate` and copy the template
with `cp .env.example .env`; the remaining commands are the same.

## Start

Run from `backend` with the virtual environment active:

```powershell
uvicorn app.main:app --reload
```

- Swagger docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

The health endpoint returns:

```json
{"status": "ok", "service": "AgriRoute API"}
```

CORS allows the development origin `http://localhost:5173`.

## Database setup and troubleshooting

`app/database.py` exposes `engine`, `SessionLocal`, `Base`, and `get_db()`.
Future routers can use `Depends(get_db)` for a request-scoped session.
Sessions are closed after use and rolled back when a request fails. Transactions
must be committed explicitly by future services.

A missing or malformed `DATABASE_URL` causes a clear startup configuration error
without printing credentials. Engine construction does not connect to PostgreSQL:
connections are opened only when database work is requested. `/health` checks API
availability, not PostgreSQL availability. If future database operations fail,
check that PostgreSQL is running and that the host, port, database, and credentials
are correct. No tables are created automatically.

## Migrations

The existing `DATABASE_URL` in `.env` is reused by Alembic. No credentials are
stored in `alembic.ini`. From `C:\FarmRoute\backend`:

```powershell
.\.venv-local\Scripts\python.exe -m pip install -r requirements.txt
.\.venv-local\Scripts\python.exe -m alembic upgrade head
.\.venv-local\Scripts\python.exe -m alembic current
.\.venv-local\Scripts\python.exe -m alembic check
.\.venv-local\Scripts\python.exe -m uvicorn app.main:app --reload
```

The initial revision is `a09f92faa2ef_initial_agriroute_schema.py`. It creates
`users`, `produce_batches`, and `buyer_requirements` in the default public schema.
Alembic also maintains its own `alembic_version` bookkeeping table. Re-running
`upgrade head` is safe when the revision is already applied. Future model changes
can be generated with `alembic revision --autogenerate -m "describe change"`;
review generated migrations before upgrading. Unrelated existing tables are
excluded from autogenerate, preventing unintended drop operations.

In your Supabase project, open Table Editor, select `public`, and refresh. The
three application tables should appear. To verify through SQL Editor:

```sql
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name IN ('users', 'produce_batches', 'buyer_requirements');
```

`http://localhost:8000/health/db` executes `SELECT 1` and reports connectivity.
Swagger exposes both health endpoints, twelve CRUD endpoints, three transaction endpoints,
and the primary matching endpoint.

Quantities use `Numeric(14,3)` and prices `Numeric(14,2)`, represented as Decimal
in Python. Coordinates use six decimal places. Create schemas reject extra fields,
including client-supplied quantity balances. SQLAlchemy INSERT defaults initialize
sold/rerouted quantities to zero and remaining quantities from their initial
values. These defaults run on INSERT/flush, not object construction; direct SQL
inserts must explicitly supply remaining quantities. Sales use the manual acceptance
endpoint below. `updated_at` is refreshed for SQLAlchemy updates, not arbitrary
raw SQL updates. Optional descriptive/date/location fields accept null; batch code,
crop, owner, quantity, quality, and price fields are required.

Run the isolated model/schema checks (no Supabase data is inserted):

```powershell
.\.venv-local\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv-local\Scripts\python.exe -m unittest discover -s tests -v
```

## Basic CRUD API

| Resource | Create/list | Read/update |
| --- | --- | --- |
| Users | POST /users, GET /users | GET /users/{user_id}, PUT /users/{user_id} |
| Produce | POST /produce, GET /produce | GET /produce/{batch_id}, PUT /produce/{batch_id} |
| Buyer requirements | POST /buyer-requirements, GET /buyer-requirements | GET /buyer-requirements/{requirement_id}, PUT /buyer-requirements/{requirement_id} |

Creation returns 201. Missing records return 404; duplicate emails return 409;
invalid user roles return 400; invalid payloads return 422. Database failures
return generic errors without database configuration or driver details.

List filters: users support `role` and `is_active`; produce supports `farmer_id`,
`crop_name`, `status`, `risk_level`; buyer requirements support `buyer_id`,
`crop_name`, `status`. Crop filters use exact matches. Results are ordered by ID.

PUT updates only supplied fields, preserves omitted fields, and permits explicit
null only for nullable columns. User email/role/ID cannot change. Produce owner,
crop, harvest date, initial quantities, balance quantities, code, and status cannot
change. Buyer owner, crop, initial/balance quantities, and status cannot change.
Swagger documents the exact allowed fields. Extra fields are rejected.

Produce creation requires a FARMER; requirement creation requires a BUYER.
The API assigns status and quantity balances and generates codes such as
`AGR-TOM-0001`. A PostgreSQL transaction advisory lock serializes code generation;
the database unique constraint additionally protects uniqueness. Prefix numbers
run from 0001 to 9999; an exhausted prefix returns 409. No new schema is required.
The buyer price range is validated against both stored and updated values.

To create/reuse the requested demo records with the server running:

```powershell
.\.venv-local\Scripts\python.exe scripts\seed_demo.py
```

The sample uses a harvest date of 2026-10-05 and a buyer price range of 20–25 per
kg because those values were not specified in the sample brief. All three users
have location Puducherry. The script prints committed IDs and quantity values.
It reuses the demo emails and matching batches/requirements on subsequent runs.
In Supabase Table Editor, choose `public` and open each of the three tables;
filter by the printed IDs to verify the records. No delete endpoint, authentication,
rerouting, AI, or frontend integration is implemented.

## Manual primary-sale acceptance

Migration `f8b85e561cb1_add_primary_sale_transactions.py` adds only `transactions`
and its indexes/constraints. Run `python -m alembic upgrade head` from the active
backend virtual environment before starting the server.

- POST `/transactions/accept`
- GET `/transactions` (optional `produce_batch_id`, `buyer_id` filters)
- GET `/transactions/{transaction_id}` (404 when missing)

Example request (apply once to the original unfulfilled demo data):

```json
{"produce_batch_id": 1, "buyer_requirement_id": 1, "quantity_kg": 600, "price_per_kg": 25}
```

The server derives buyer ID, `PRIMARY_SALE` type, and `ACCEPTED` status. Extra
fields are rejected. Price is optional and must be nonnegative if supplied;
omitted price is recorded as null. Crop names use case-insensitive exact matching.
Missing records return 404, invalid buyer/crop returns 400, insufficient quantities
or blocked statuses return 409, and invalid numeric/request fields return 422.

Acceptance owns one database transaction and locks produce first, then buyer
requirement with PostgreSQL `FOR UPDATE`. Validation, quantity updates, transaction
insert, refresh, and response validation occur before commit. Failures roll back
both balances and the transaction record. No intermediate writes are committed.
All acceptance calls use the same lock order. Quantities are Decimal, never float.

After the demo sale, produce ID 1 has initial 1000.000, sold 600.000, remaining
400.000, rerouted 0.000, status PARTIALLY_SOLD. Requirement ID 1 has required
600.000, remaining 0.000, status FULFILLED. Repeating the sale is rejected;
primary recommendations can now be recalculated for Remaining Inventory, without
automatic acceptance or processor sales.

In Supabase Table Editor, select public and inspect `transactions`, produce ID 1,
and requirement ID 1. The acceptance endpoint is not an idempotent request API:
check the transaction list and quantities before retrying an uncertain response.
Tests use an isolated SQLite database for functional and rollback cases; PostgreSQL
provides the actual row-locking behavior in production.

The demo acceptance was applied as transaction ID 1 (buyer ID 2, produce ID 1,
requirement ID 1, quantity 600.000, price 25.00, PRIMARY_SALE, ACCEPTED).
All 17 automated tests passed. Live Supabase checks verified the transactions
table, PostgreSQL row-lock exclusion on both records, unchanged quantities after
rejected requests, committed sale balances, transaction reads, health, and docs.

## Primary buyer recommendations and re-matching

GET `/matches/produce/{batch_id}` dynamically ranks eligible primary buyer
requirements. No matches table or migration is added. Missing batch returns 404;
no eligible buyers, unavailable produce, or zero Remaining Inventory returns an
empty `matches` array. Recommendations never reserve quantities or write data.
The existing acceptance endpoint rechecks quantities under row locks at sale time.

All weights and constants live in `app/services/matching_service.py`:

| Component | Weight | Rule (component range 0–100) |
| --- | --- | --- |
| Crop | 10% | Case-insensitive exact match is mandatory; compatible = 100. |
| Quantity | 20% | 100 × min(produce remaining, buyer remaining) / produce remaining. Smaller buyer quantities remain eligible. |
| Quality | 20% | A > B > C; satisfying minimum = 100; known incompatible grades excluded; unknown = 50 with warning. |
| Price | 20% | Inside buyer range = 100; outside score drops linearly to 0 at 25% deviation from nearest bound; beyond 25% excluded. Denominator is at least 1 to handle zero bounds. Missing = 50. |
| Distance | 10% | Haversine, Earth radius 6371.0088 km. Beyond specified maximum excluded; within maximum = 100 − 50 × distance/maximum. Without maximum = max(0, 100 − distance). Missing coordinates = 50, distance null. |
| Pickup | 10% | Past/before-harvest or beyond availability excluded. Known valid window: max(0, 100 − 10 × days until pickup). Missing pickup/window = 50. Expired availability excluded. |
| Urgency | 10% | Risk intensity LOW 0, MEDIUM .25, HIGH .65, CRITICAL 1. Score = (1 − intensity) × 50 + intensity × quickness × compatibility / 100; compatibility averages quality, price, distance. |

Quickness is max(0, 100 − 10 × days until valid pickup); missing pickup = 50.
Current dates use India time. Future harvest dates establish earliest pickup.
The weighted average is rounded to two decimals; ties use requirement ID ascending.
Missing information is returned in `warnings` for human confirmation. Scores are
transparent prototype rules and make no AI predictions. Monetary balances stay
Decimal; floating point is used only for geographic calculations and ranking scores.

Eligibility requires an active BUYER, OPEN/PARTIALLY_FILLED requirement with positive
remaining quantity, and the mandatory crop gate. Completed/cancelled/rerouting
produce is excluded. Known quality, price, distance, or timing incompatibilities
are excluded as documented above.

Run the Buyer B demo with the server running:

```powershell
.\.venv-local\Scripts\python.exe scripts\demo_primary_rematch.py
```

It creates/reuses Green Basket Retail (`greenbasket@agriroute.demo`) and a 250 kg
Tomato requirement with minimum A, price 20–30, maximum distance 50 km, pickup
2026-10-06, and Puducherry coordinates 11.9416/79.8083. Produce coordinates remain
unchanged, so its distance is null. The script verifies the recommendation and
accepts 250 kg using `/transactions/accept`; reruns reuse an existing sale.
After the sale, produce has initial 1000.000, sold 850.000, Remaining Inventory
150.000, rerouted 0.000, status PARTIALLY_SOLD. Buyer B is FULFILLED. Recalling
the matching endpoint recalculates candidates from current balances; it does not
automatically sell or reroute the 150 kg. No processor/alternative-market matching,
AI, authentication, or frontend integration is implemented.
