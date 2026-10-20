# Phase 14 — Role account onboarding

The login page now supports self-service registration through the existing
`POST /auth/register` endpoint. A new user can create a Farmer, Primary Buyer,
or Processor account, then the page signs in through the normal FastAPI login
and `/auth/me` verification flow before opening the role workspace.

The registration form collects name, email, optional phone, role, and a password
of at least 12 characters with confirmation. Passwords are sent only to FastAPI
over the configured API connection, are not stored in browser storage, and are
cleared from the form after submission. Backend role authorization remains
authoritative. ADMIN is deliberately not offered: `POST /auth/register` rejects
administrator accounts, which must be provisioned by a trusted operator.

## Run

Configure the backend as described in [Phase 12](../backend/docs/phase12.md),
start FastAPI, and set `VITE_API_BASE_URL` as described in
[Phase 13A](phase13a.md). Open `/login`, choose **Create an account**, and submit
the details for a non-admin role. The backend database must be configured and
reachable before registration can succeed.

For the first administrator in a new database, use the backend's interactive
bootstrap from a private terminal after setting `DATABASE_URL` and `JWT_SECRET`
in `backend/.env`:

```powershell
cd backend
.\.venv-local\Scripts\python.exe -m scripts.create_admin
```

The script prompts for the administrator's name, email, and password without
echoing the password. It refuses non-interactive execution and never prints the
password or its hash. Keep the `.env` file out of source control.

## Boundaries

- Registration creates active accounts immediately, matching the current
  backend endpoint behavior. There is no email verification or approval queue.
- Password reset, account recovery, administrator creation UI, rate limiting
  across multiple API instances, and account deletion remain future work.
- The role workspace only shows records available to that account. New accounts
  start with no produce, requirements, or transaction history.

## Verification status

This phase was implemented in the frontend during the current work session.
Automated tests and a production build were not run in this session. Live
registration requires a running backend connected to the new Supabase project.
