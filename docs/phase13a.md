# Phase 13A — React authentication through FastAPI

Only login, session identity, access guards and logout are integrated. All
dashboard produce, requirements, allocations, statistics and workflows still use
the original local mock store. No dashboard API calls, Supabase client, schema
migration or AI were introduced. All existing stylesheets and dashboard page
files are unchanged. The login story, role cards and shared shell retain their
existing classes; credential inputs use existing Field/panel/button styles.

## Run

Copy `.env.example` to `.env.local` and configure:

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:8000
```

The local `.env.local` contains only that public API URL. Never place credentials,
JWT signing secrets or database strings in VITE variables. Restart Vite after
changing environment configuration.

```powershell
# From C:\FarmRoute
npm install
npm run dev -- --port 5173 --strictPort
```

Open http://localhost:5173/login. Keep FastAPI running on port 8000 using the
backend README instructions. CORS on the running API permits exactly the existing
development origin http://localhost:5173; a live OPTIONS preflight returned 200.
No unrestricted CORS setting was introduced. Opening the frontend by a LAN IP or
127.0.0.1 instead of localhost would require an explicitly approved origin.

## Login, identity and permissions

The fetch client centralizes URL configuration, JSON bodies, bearer headers,
15-second request timeout, cancellation and safe errors. POST `/auth/login` sends
only email/password and deliberately omits any old Authorization header.
GET `/auth/me` verifies the returned bearer token. The token is persisted only
after an active, supported backend profile has been verified.

AuthProvider exposes user, token, isAuthenticated, loading, login and logout.
Only id/name/email/role/is_active are retained as the profile. Passwords are held
only in the controlled login input/request and cleared after submission. No
credential or token is embedded in source, fixtures or documentation. Automated
frontend tests generate disposable credentials and tokens at runtime.

The four role cards now focus the credentials form and indicate a perspective;
they do not authenticate or determine the destination. The legacy selectRole
function was removed and its localStorage marker is cleared. Real `/auth/me`
roles redirect as follows:

| Backend role | Destination |
|---|---|
| FARMER | `/farmer/dashboard` |
| BUYER | `/buyer/dashboard` |
| PROCESSOR | `/processor/dashboard` |
| ADMIN | `/admin/dashboard` |

All four workspace prefixes, including unknown nested pages, have a shared
ProtectedRoute. Unauthenticated visitors go to `/login`; another role's workspace
redirects to the authenticated role's own dashboard. Pending restoration shows a
session check rather than rendering protected content. Backend authorization
remains authoritative; these UI guards do not grant API privileges.

## Prototype token storage and session behavior

Tokens use per-tab sessionStorage, preserving a session through refresh. No
cached user or selected role is used as identity. Refresh calls `/auth/me` again.
An invalid/expired/inactive-account response clears authentication and returns to
login. Failed restoration due to a network error also fails closed and requires
sign-in again. Expiration timers and visibility checks clear expired UI sessions;
JWT claims are used only to schedule expiry, never to grant identity or role.
An authenticated 401 clears the corresponding active session. A stale request
from a different token cannot log out a newer session.

Login requests are deduplicated in both the form and provider. Inputs/buttons are
disabled while checking/signing in. Logout cancels pending login and prevents late
responses from restoring the session. Existing workspace/profile controls now
perform logout, have an accessible Log out label, clear token/user and redirect
to `/login`. Dashboard localStorage inventory is preserved; logout makes no
backend mutation.

sessionStorage is a prototype choice and is accessible to JavaScript; XSS could
expose tokens. Use HTTPS and application security controls in production. A
future deployment should assess HTTP-only cookies/session handling and CSRF
protections. Backend access tokens are not remotely revoked by local logout;
they retain the backend's configured lifetime. No registration UI, password reset
or refresh-token integration was added.

## Verification

```powershell
npm test
npm run build
```

Frontend tests use the actual API client, AuthProvider, Login, ProtectedRoute,
DashboardLayout and App with disposable mocked HTTP responses. They cover all
four role redirects, ignoring selected role, pending/duplicate submissions,
invalid credentials, network failures, `/auth/me` verification, inactive/unknown
roles, refresh including StrictMode, expired/invalid tokens, all protected
workspace prefixes, cross-role redirects, logout, stale 401 handling and late
login cancellation. They assert that no dashboard data APIs are called.

All 27 frontend authentication tests passed, and the production build succeeds. All 149 backend tests also passed with isolated
Supabase and live verification enabled, including the existing real-JWT tests.
The existing non-failing TestClient/httpx deprecation warning remains. Live
FastAPI CORS and frontend `/login` HTTP checks returned 200. No backend source or
database schema was modified for this phase.

The browser automation runtime failed to initialize, so a visual browser check
could not be completed. CSS and existing dashboard page diffs are empty. The
activated passwords for demo users 1, 2 and 3 were not supplied through a private
credential file; they were not guessed, read from hashes or reset. Live browser
login with those specific accounts remains a manual acceptance check:

1. Sign in as Arun Kumar using the privately activated account credentials;
   confirm `/farmer/dashboard` and the authenticated header name.
2. Refresh and confirm the session remains. Try `/buyer/dashboard`; confirm the
   farmer dashboard is restored. Use the workspace/profile Log out control.
3. Sign in as FreshMart Wholesale and confirm `/buyer/dashboard`.
4. Log out, sign in as South Foods Processing and confirm `/processor/dashboard`.
5. Test a deliberately incorrect password and confirm the clear error. After
   logout, opening any protected route must return to `/login`.

Do not capture screenshots containing credentials or paste passwords into docs.
The dashboard data shown during these checks is still simulated.

## Files

Created: `.env.example`, `src/api/config.js`, `src/api/client.js`,
`src/auth/tokenStorage.js`, `src/auth/service.js`, `src/auth/AuthContext.jsx`,
`src/auth/ProtectedRoute.jsx`, `vitest.config.js`, `tests/frontend/setup.js`,
`tests/frontend/auth.test.jsx`, and `docs/phase13a.md`.

Modified: `src/main.jsx`, `src/App.jsx`, `src/hooks/useStore.jsx`,
`src/pages/public/Public.jsx`, `src/layouts/DashboardLayout.jsx`, `package.json`,
`package-lock.json` and root `README.md`. Private ignored `.env.local` configures
the local API URL. No farmer dashboard data integration was started.
