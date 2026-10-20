# Phase 16 — Administrator account access

The admin dashboard now includes an account-access panel backed by the existing
`GET /users` and `PUT /users/{user_id}` endpoints. Administrators can search by
name, email, or phone; filter by role and active status; and activate or
deactivate accounts after reviewing a confirmation prompt. Deactivation
preserves account and business history while the authentication service denies
future sign-ins.

The API rejects self-deactivation and prevents deactivation of the last active
administrator. The UI mirrors those safeguards to explain why a control is
disabled, but server-side checks remain authoritative. Account creation,
password recovery, role changes, and deletion are outside this phase.

## Verification status

The UI and API safeguards were implemented in the current work session. The
frontend suite and backend tests were not run. Live account changes require the
local `DATABASE_URL` password placeholder to be replaced and an active admin
account to sign in.
