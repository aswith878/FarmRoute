# Phase 13B — Role workflows connected to FastAPI

Phase 13B begins the transition from the local demo store to the authenticated
FastAPI service. The shared React store now fetches account-scoped data from the
API. It does not read dashboard inventory, buyer requirements, or allocations
from localStorage.

## Connected workflows

- **Farmer:** list produce, review server-backed inventory and traceability,
  view API-ranked primary buyer requirements, record primary allocations,
  record real matching attempts, and review API-calculated routing readiness.
- **Buyer:** create a buyer requirement, view produce returned for that account's
  active requirements, revise its match criteria, and accept a partial quantity
  through the transaction API.
- **Processor:** create a processing requirement, review scoped routing cases and
  processor matches, revise its match criteria, record an explicit condition
  and utilization assessment, then accept the compatible quantity with an
  idempotency key.
- **Admin:** view active account counts, produce balances, primary transactions,
  risk labels, traceability events, and account access state from the API.

The browser sends requests to FastAPI only. FastAPI remains responsible for
authentication, role authorization, ownership, match scoring, inventory
calculations, routing eligibility, and transaction writes. Failed network loads
are displayed as errors instead of silently presenting demo inventory.

## Current boundaries

- Phase 13B replaces the old guided demo actions. Restarting sample inventory
  and simulating Day 3 are no longer actions in the live routing screen. A farmer
  can record an actual matching attempt; the API decides whether a routing case
  can be opened.
- Produce listing photos are uploaded through the Phase 15 API/Storage flow.
  The visual assessment is still a fixed prototype sample.
- Admins can activate and deactivate accounts through the Phase 16 account
  management screen. New account creation and initial administrator
  provisioning remain operator tasks documented by the backend.
- The dashboards use existing API records and endpoints; no dedicated analytics
  endpoint, pagination, or export workflow has been added.
- Authenticated browser acceptance requires an activated user and a running API
  configured for the frontend origin. The browser session token remains in
  `sessionStorage`, as documented for Phase 13A.

## Verification

This phase was not run through the frontend test suite or a production build in
this work session. Live acceptance needs the user's FastAPI service, matching
frontend origin, activated role accounts, and sample database records. Verify
each role with the workflow list above before treating Phase 13B as accepted.
