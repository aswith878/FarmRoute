# Phase 12 — FastAPI JWT authentication and access control

Supabase remains the PostgreSQL provider. Authentication is implemented by
FastAPI, PyJWT and Argon2; Supabase Auth is not used. React remains unchanged and
uses mock data. No frontend integration or AI was added.

## Configuration and startup

Run from `C:\FarmRoute\backend`:

```powershell
.\.venv-local\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv-local\Scripts\python.exe -m alembic upgrade head
.\.venv-local\Scripts\python.exe -m uvicorn app.main:app --reload
```

`backend/.env` contains `DATABASE_URL` and:

```dotenv
JWT_SECRET=<your independently generated random secret>
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
```

For the new AgriRoute Supabase project, `DATABASE_URL` uses the shared
transaction-mode pooler for API requests, while `DIRECT_URL` uses the
session-mode pooler for Alembic migrations. Both example values are in
`.env.example`; replace `[YOUR-PASSWORD]` in each with the database password
from Supabase. `DIRECT_URL` is used by `alembic upgrade head` and schema
inspection. Do not leave the placeholder in place or commit `backend/.env`.

Generate a secret once using Python's `secrets.token_urlsafe(48)` and store it in
the private `.env` or a production secret manager. Never commit or share it.
The local private `.env` was configured with a freshly generated random secret;
it is not included in this documentation. Startup rejects a missing/short secret
or expiration outside 1–1440 minutes. Only HS256 is accepted; algorithm selection
is not taken from an untrusted token. Tokens require subject, issued-at,
expiration, issuer `agriroute-api`, and audience `agriroute`.

## Endpoints and token workflow

| Endpoint | Access | Behavior |
|---|---|---|
| POST `/auth/register` | Public | Create FARMER, BUYER or PROCESSOR; reject ADMIN with 403 |
| POST `/auth/login` | Public | JSON email/password; return bearer access_token, expires_in seconds and expires_at UTC |
| GET `/auth/me` | Bearer token | Return safe UserRead profile without credentials |
| GET `/health`, GET `/health/db` | Public | Existing health responses unchanged |
| `/docs`, `/redoc`, `/openapi.json` | Public | API documentation only; operations retain their own protection |
| All business endpoints | Bearer token | Role and record ownership checks |

Registration retains name, email, role, optional phone, location_name, latitude
and longitude. Passwords require 12–128 characters. Password whitespace is
preserved. Emails are normalized to lowercase and a unique `lower(email)` index
prevents concurrent case-insensitive duplicates. Unknown, incorrect, inactive
and unactivated account credentials receive the same 401 response. Missing or
invalid tokens return 401 with WWW-Authenticate: Bearer. Role/owner violations
return 403; normal business conflicts still return 409.

Send `Authorization: Bearer <access_token>` with protected requests. In Swagger,
call `/auth/login`, copy access_token, click **Authorize**, and paste the token
without the `Bearer` prefix. The HTTP bearer security scheme is included on every
business operation and `/auth/me`.

Argon2id salted hashes are stored in users.password_hash. Login verifies them
and upgrades outdated hashing parameters. last_login_at records successful login.
UserRead explicitly excludes both the hash and password. Missing-account login
performs dummy Argon2 verification to reduce timing differences. Tokens contain
only identity/timing/issuer/audience claims; roles and active state are reread from
the database on every authenticated request. Tokens and signing secrets are
never logged by application code. Validation and database error responses omit
submitted input and driver details.

## Permissions

| Role | Permissions |
|---|---|
| FARMER | Create produce using own farmer_id; list/read/update own produce; own matches, matching attempts, readiness, rerouting and timelines; own routing cases and associated primary/alternative allocation history |
| BUYER | Create/list/read/update own buyer requirements; discover produce compatible with own requirements; record rejection against own requirement; accept primary quantities only against own requirement; own transactions |
| PROCESSOR | Create/list/read/update own processor requirements; discover eligible active cases for own requirements; own scoped suitability assessments and recommendations; accept against own requirement; own allocations |
| ADMIN | Manage users and business records; perform authorized administrative business operations |

User collection/create/update are admin-only. Non-admin users can read their own
user profile. Owner IDs remain in existing business schemas for compatibility,
but must equal the authenticated user's ID. ADMIN may explicitly assign another
valid owner. Existing schemas continue to forbid changes to role/email/owner IDs,
server-controlled quantities, statuses and other protected fields.

Collection scopes are applied in SQL and combined with submitted filters, so an
owner-ID filter cannot widen access. Buyer produce discovery applies existing
primary compatibility rules. Processor case discovery checks open own
requirements, remaining inventory, crop, condition, quality, price, distance and
pickup compatibility; suitability is deliberately not required before discovery
because an assessment must be recorded first. Full existing suitability and
matching checks still apply before allocation. Opportunity discovery does not
grant access to another farmer's private timeline or another user's requirements.

Authentication reads use a separate session from atomic business services.
Primary acceptance rechecks buyer ownership after locking the buyer requirement.
Alternative acceptance rechecks processor ownership after locking the requirement
and also before returning an idempotent prior allocation. Suitability checks
ownership after locks. Locked services retain the original quantity arithmetic,
lock ordering, rollback behavior and event recording. Trusted local service calls
can operate without an HTTP actor; this is not an exposed API bypass.

## Processor suitability and updates

Processor calls to `/routing-cases/{case_id}/suitability` must include
`processor_requirement_id` owned by the token holder and matching the declared
utilization. Assessor name and ID come from authenticated identity, not client
claims. Assessments are stored under
`trigger_details.processing_suitability_by_requirement`; a processor's decision
does not authorize another processor's requirement. Processors see only their own
scoped assessment details/recommendations. Existing case-wide admin assessments
remain compatible and are preserved. Traceability includes scoped assessments.

PUT `/processor-requirements/{requirement_id}` permits own compatible quality,
condition, utilization, price, distance, pickup and location updates. Owner,
quantity, remaining balance, crop and status remain server controlled. A merged
price-range check runs while the requirement is locked.

## Legacy accounts and local activation

Migration `e9e552718ba4` adds nullable password_hash and last_login_at plus the
case-insensitive email index. It does not recreate tables or update records.
All seven existing accounts remain unactivated. In particular users 1–4 and all
their transaction/history references remain intact. No demo/default password was
assigned. A legacy user with no hash cannot log in or use a token.

In an interactive local terminal, activate an existing active account:

```powershell
.\.venv-local\Scripts\python.exe -m scripts.activate_user 1
```

Enter a private password twice at the non-echoing prompts. The password is not a
command argument and no hash is displayed. The CLI locks and updates only the
selected user's hash (and its normal updated_at timestamp). It does not change
role, active status, ownership, inventory or history. Noninteractive invocation
is rejected to prevent password echo fallback. Database failures are sanitized.
Repeat with the desired existing account ID; activation was **not** performed on
live users during verification.

For the first ADMIN, a trusted local operator may explicitly run:

```powershell
.\.venv-local\Scripts\python.exe -m scripts.create_admin
```

This prompts for name/email and a private confirmed password. It creates a new
ADMIN only when deliberately run locally. It is not exposed through public
registration, startup or migration. No live administrator was automatically
created. Protect server/CLI filesystem access as an administrative capability.

## Production security requirements and limitations

Before exposing public registration/login to the internet, deploy a shared
gateway or Redis-backed rate limiter. Apply a login limit of 5 failed attempts
per normalized email per 15 minutes and 30 attempts per client IP per 15 minutes;
apply registration limits of 5 per IP per hour. Enforce atomic counters across
workers, return 429 with Retry-After, use progressive delay rather than permanent
account lockout, and alert on sustained failures. Hash email/IP limiter keys,
keep identifiers out of logs, and use only trusted proxy-provided client IPs.
Do not use process-local counters in a multiworker deployment. Test these gateway
rules before publishing; no distributed rate limiter is bundled in this phase.

Use HTTPS, restrict trusted origins/proxies, provision and rotate strong secrets,
keep SQLAlchemy SQL/parameter logging disabled and redact Authorization headers
in gateway/application monitoring. Token storage is a future frontend integration
decision. There are no refresh tokens, logout/revocation list, MFA, email ownership
verification or remote password reset in this phase. Deactivation takes effect on
the next request; password reset does not revoke previously issued access tokens,
which expire within the configured TTL. Rotate the signing secret to invalidate
all existing tokens when needed. Re-enable users only through an authorized admin.

Opportunity collection discovery currently evaluates candidates in Python before
applying the result IDs as SQL scope; add pagination/query optimization for large
datasets without weakening ownership/compatibility rules. Existing admin CRUD
and authentication migrations can run without launching the app; there is no
authentication bypass controlled by an environment flag.

## Automated and live verification

From the backend directory:

```powershell
$env:AGRIRoute_POSTGRES_TESTS='1'
$env:AGRIRoute_LIVE_VERIFY='1'
.\.venv-local\Scripts\python.exe -m unittest discover -s tests -q
```

Existing 109 business tests use a trusted test-only ADMIN fixture; real JWT tests
do not override authentication. Dedicated tests cover registration/login, Argon2
storage, safe profiles, invalid/expired/missing/wrong-algorithm tokens, inactive
and legacy users, role enforcement, owner spoofing, cross-user reads/updates,
SQL-scoped lists, unauthorized primary/alternative transactions with preserved
inventory, independent locked service ownership, requirement-scoped suitability,
idempotency, local activation and OpenAPI security. Supabase tests use isolated
schemas and real JWTs; concurrent registrations prove the unique email invariant.
Existing PostgreSQL allocation/rerouting/event concurrency tests remain included.

Live verification compares pre/post row digests across all 10 application tables
without exposing row contents. All seven users, three primary transactions, one
allocation and their original sources remain unchanged. Batch 1 remains
1000/850/150/0 kg (initial/sold/remaining/rerouted), LOW risk, one failed attempt,
rerouting 409. Batch 2 remains 1000/850/0/150 kg. Timeline event counts remain four
and seven, respectively. Migration columns are nullable; all legacy hashes and
login timestamps remain NULL. Frontend Git diff is empty.

Final suite count and real HTTP checks are recorded in the README after execution.


Final verification: **149 tests passed with zero skips**, including all 109
previous tests. Alembic check found no new upgrade operations. A real uvicorn
server started without import errors. `/health`, `/health/db`, `/docs` and
`/openapi.json` returned 200; protected endpoints without tokens returned 401.
Real JWT login and profile access passed against isolated Supabase data. The
verification server was stopped after checks. Only the existing third-party
TestClient/httpx deprecation warning and intentional sanitized failure-test logs
were emitted. No unresolved functional errors were encountered.

## Files created or modified

All paths below are relative to `backend/`.

Created:

- `app/core/security.py`, `app/core/auth.py`, `app/core/access.py`
- `app/schemas/auth.py`, `app/routes/auth.py`
- `alembic/versions/e9e552718ba4_add_user_credentials_and_case_.py`
- `scripts/activate_user.py`, `scripts/create_admin.py`
- `tests/auth_support.py`, `tests/test_auth.py`, `tests/test_auth_postgres.py`
- `docs/phase12.md`

Modified:

- `app/main.py`, `app/models/user.py`, `app/schemas/processor.py`
- `app/routes/users.py`, `app/routes/produce.py`, `app/routes/buyer_requirements.py`
- `app/routes/transactions.py`, `app/routes/matches.py`, `app/routes/risk_tracking.py`
- `app/routes/routing_cases.py`, `app/routes/processors.py`, `app/routes/traceability.py`
- `app/services/transactions.py`, `app/services/alternative_acceptance_service.py`
- `app/services/processor_matching_service.py`, `app/services/traceability_service.py`
- `app/services/rerouting_service.py`, `app/services/risk_service.py`
- `tests/test_crud.py`, `tests/test_phase9_postgres.py`
- `requirements.txt`, `.env.example`, `.gitignore`, `README.md`

Private local configuration: `.env` received a generated JWT signing secret and
expiration setting. `.phase12-before.json` contains only preservation counts and
hashes and is ignored by Git. Neither private file is needed in source control.
No frontend file was edited.
