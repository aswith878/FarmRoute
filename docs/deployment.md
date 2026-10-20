# Deployment and production handoff

The repository includes a Vercel SPA config, a Render Blueprint for the FastAPI service, and a GitHub Actions workflow that runs frontend tests/build plus the backend suite. The Render Blueprint uses the Singapore region, runs the Alembic head migration before deployment, and gates traffic on `/health/db`. It only deploys after repository checks pass and prompts for database URLs, the server-only Supabase Storage key, and the production frontend origin instead of storing credentials in source control.

## Deploy the API

1. Push this repository to a Git provider connected to Render and create a Blueprint from `render.yaml`.
2. Supply `DATABASE_URL` using the Supabase transaction-mode pooler (port 6543) and `DIRECT_URL` using the session-mode pooler (port 5432). URL-encode reserved characters in the database password. Keep the values in Render's secret environment settings.
3. Supply a newly rotated Supabase server-only service-role/secret key. The key previously pasted into chat must be revoked. Keep it out of Vercel, browser variables, and source control.
4. Set `AGRIROUTE_CORS_ORIGINS` to the exact Vercel deployment origin, including `https://` and no path. Add a comma-separated list only if multiple production origins are intentionally used.
5. Check the Render deployment logs and verify `/health` and `/health/db` return HTTP 200. The pre-deploy step applies pending Alembic migrations.

## Deploy the frontend

1. Import the repository into Vercel as a Vite project. The checked-in `vercel.json` builds `dist` and supports client-side route deep links.
2. Set `VITE_API_BASE_URL` in the Vercel Production environment to the deployed FastAPI service origin, with no trailing path. Trigger a fresh build because Vite embeds this value at build time.
3. Add that exact Vercel origin to the Render `AGRIROUTE_CORS_ORIGINS` setting and redeploy the API.
4. Sign in with a privately provisioned active administrator and run the role walkthrough below.

## Live acceptance walkthrough

- Create or activate one account for each role and verify role-specific routes are guarded.
- Farmer: create a produce batch, upload a photo, confirm a batch code, view matching, and verify timeline events.
- Buyer: create and edit a requirement, accept a compatible partial quantity, verify both balances, and cancel an active requirement.
- Processor: create and edit a requirement, assess compatible produce, accept an allocation, verify allocation history and totals, and cancel an active requirement.
- Admin: inspect scoped network data and deactivate/reactivate a non-admin account; confirm self-deactivation and last-admin protections.
- Confirm browser requests target the deployed API and that no Supabase service key appears in frontend assets or network requests.

## Current external handoff

The Supabase project is active, its schema and migrations are present, application tables have RLS enabled, and the `anon` and `authenticated` database roles have no SELECT permission on application user records. Business access is intentionally mediated by FastAPI's authenticated ownership checks. The service-role credential and database password previously shared in chat must be rotated in Supabase before production use. Then update the Render secrets and run the live acceptance walkthrough. This workspace has no connected Vercel or Render deployment account, so deployment itself must be initiated from those dashboards.
