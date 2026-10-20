# Phase 17 — Buyer and processor requirement management

Buyers can now edit the quality, price range, distance, pickup date, and
location criteria on their existing requirements. Processors can edit quality,
accepted produce conditions, intended utilization, price range, distance,
pickup date, and location for their own requirements. Crop and requested
quantity remain fixed after creation because the backend update schemas do not
permit those fields to change.

Both screens use the existing owner-scoped FastAPI `PUT` operations. The API
continues to validate price ranges under a row lock, and the frontend refreshes
only the matching requirement in local state after a successful update.

## Verification status

The buyer and processor management controls were implemented in the current
work session. Automated tests and a production build were not run. Live updates
require an authenticated account and a reachable backend connected with a
valid PostgreSQL password in `backend/.env`.
