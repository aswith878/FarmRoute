# Phase 18 — Requirement cancellation

Buyers and processors can cancel active requirements they own. Cancellation is available only for OPEN or PARTIALLY_FILLED requirements; it preserves prior transactions and allocations while removing the requirement from future matching. The API locks the requirement during transition and returns HTTP 409 for repeat cancellation or any non-active state.

The buyer and processor dashboards retain cancelled requirements as history and offer cancellation only for active records. Authorization coverage verifies owner scoping, successful cancellation, and rejection of repeat cancellation.
