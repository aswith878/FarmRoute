"""Create eligible routing cases only; no inventory movement or matching."""
from dataclasses import asdict

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.risk_config import RULES
from app.core.auth import enforce_owner
from app.models.enums import UserRole
from app.models import ProduceBatch, RoutingCase
from app.models.routing_case import RoutingCaseStatus
from app.schemas.risk_tracking import RoutingReadiness
from app.services.risk_service import evaluate_readiness
from app.services.traceability_service import record_event

ACTIVE_CASE_STATUSES = (
    RoutingCaseStatus.AWAITING_ALTERNATIVE_MATCH,
    RoutingCaseStatus.MATCHED,
)


def request_rerouting(db: Session, batch_id: int) -> RoutingCase:
    """Own one transaction on a fresh session and return a detached case snapshot.

    Readiness is recalculated even on retries. Eligible retries return the existing
    active case unchanged. The batch lock serializes requests with acceptance and
    tracking writes; the partial unique index is an additional concurrency guard.
    No produce attributes or quantity balances are assigned by this service.
    """
    try:
        with db.begin():
            batch = db.scalar(
                select(ProduceBatch)
                .where(ProduceBatch.id == batch_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if batch is None:
                raise HTTPException(status_code=404, detail="Produce batch not found.")
            enforce_owner(db.info.get('actor'), batch.farmer_id, UserRole.FARMER)
            if batch.remaining_quantity_kg <= 0:
                raise HTTPException(status_code=409, detail="No remaining inventory is available.")

            readiness = evaluate_readiness(db, batch)
            if not readiness['rerouting_candidate']:
                raise HTTPException(status_code=409, detail="Produce batch is not eligible for a routing case.")

            case = db.scalar(
                select(RoutingCase)
                .where(
                    RoutingCase.produce_batch_id == batch.id,
                    RoutingCase.status.in_(ACTIVE_CASE_STATUSES),
                )
                .with_for_update()
            )
            if case is None:
                # JSON mode converts Decimal quantities into exact strings for JSONB.
                details = RoutingReadiness.model_validate(readiness).model_dump(mode='json')
                details['rule_thresholds'] = asdict(RULES)
                case = RoutingCase(
                    produce_batch_id=batch.id,
                    quantity_kg=batch.remaining_quantity_kg,
                    trigger_reason='ROUTING_READINESS_ELIGIBLE',
                    trigger_details=details,
                    risk_level_at_creation=batch.risk_level,
                    status=RoutingCaseStatus.AWAITING_ALTERNATIVE_MATCH,
                )
                db.add(case)
                db.flush()
                db.refresh(case)
                record_event(db,batch,'RISK_REVIEWED','routing_case',case.id,timestamp=case.created_at,metadata=details)
                record_event(db,batch,'ROUTING_CASE_CREATED','routing_case',case.id,quantity=case.quantity_kg,timestamp=case.created_at,metadata={'trigger_reason':case.trigger_reason,'trigger_details':details})
            # Keep returned attributes available after commit/session close without
            # a post-commit query that could fail after a successful write.
            db.expunge(case)
        return case
    except IntegrityError:
        # db.begin has rolled back; never expose database constraint/driver details.
        raise HTTPException(status_code=409, detail="Routing case conflicts with existing data.") from None
