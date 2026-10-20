"""Explicit tracking and read-only routing readiness; never reroutes inventory."""
import hashlib
import json
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.core.risk_config import RULES
from app.core.auth import enforce_owner
from app.models import ProduceBatch, BuyerRequirement, User, MatchingAttempt, BuyerRejection
from app.models.enums import ProduceStatus, RequirementStatus, UserRole
from app.schemas.risk_tracking import MatchingAttemptRead, RejectionRead
from app.services.matching_service import find_primary_matches
from app.services.traceability_service import record_event


def locked_batch(db, batch_id):
    batch = db.scalar(select(ProduceBatch).where(ProduceBatch.id == batch_id).with_for_update())
    if batch is None:
        raise HTTPException(404, "Produce batch not found.")
    if batch.remaining_quantity_kg <= 0 or batch.status in {ProduceStatus.COMPLETED, ProduceStatus.CANCELLED, ProduceStatus.REROUTING}:
        raise HTTPException(409, "Produce batch has no available primary inventory.")
    return batch


def record_matching_attempt(db: Session, batch_id: int, rules=RULES):
    with db.begin():
        batch = locked_batch(db, batch_id)
        enforce_owner(db.info.get('actor'), batch.farmer_id, UserRole.FARMER)
        previous = db.scalar(select(MatchingAttempt).where(MatchingAttempt.produce_batch_id == batch_id).order_by(MatchingAttempt.attempted_at.desc(), MatchingAttempt.id.desc()).limit(1))
        now = datetime.now(timezone.utc)
        attempted = previous.attempted_at if previous else None
        if attempted and attempted.tzinfo is None:
            attempted = attempted.replace(tzinfo=timezone.utc)
        if attempted and (now-attempted).total_seconds() < rules.cooldown_seconds:
            result, reused = MatchingAttemptRead.model_validate(previous), True
        else:
            matches = find_primary_matches(db, batch)['matches']
            record = MatchingAttempt(produce_batch_id=batch_id, attempted_at=now, matching_type='PRIMARY', compatible_buyers_found=len(matches), remaining_quantity_at_attempt=batch.remaining_quantity_kg, outcome='MATCHES_FOUND' if matches else 'NO_MATCH')
            db.add(record)
            db.flush()
            db.refresh(record)
            record_event(db,batch,'PRIMARY_MATCH_ATTEMPTED','matching_attempt',record.id,quantity=record.remaining_quantity_at_attempt,timestamp=record.attempted_at,metadata={'outcome':record.outcome,'compatible_buyers_found':record.compatible_buyers_found})
            result, reused = MatchingAttemptRead.model_validate(record), False
    return result, reused


def record_rejection(db: Session, batch_id: int, payload):
    canonical = [batch_id, payload.buyer_requirement_id, payload.reason, format(payload.rejected_quantity_kg.normalize(), 'f'), payload.notes or '']
    fingerprint = hashlib.sha256(json.dumps(canonical, ensure_ascii=True).encode()).hexdigest()
    with db.begin():
        batch = locked_batch(db, batch_id)
        actor = db.info.get('actor')
        if actor is not None:
            owned_requirement = db.scalar(select(BuyerRequirement).where(BuyerRequirement.id == payload.buyer_requirement_id).with_for_update())
            if owned_requirement is None:
                raise HTTPException(404, 'Buyer requirement not found.')
            enforce_owner(actor, owned_requirement.buyer_id, UserRole.BUYER)
        previous = db.scalar(select(BuyerRejection).where(BuyerRejection.fingerprint == fingerprint))
        if previous:
            result, reused = RejectionRead.model_validate(previous), True
        else:
            requirement = db.scalar(select(BuyerRequirement).where(BuyerRequirement.id == payload.buyer_requirement_id).with_for_update())
            if requirement is None:
                raise HTTPException(404, "Buyer requirement not found.")
            buyer = db.get(User, requirement.buyer_id)
            if buyer is None or buyer.role != UserRole.BUYER or not buyer.is_active or requirement.status not in {RequirementStatus.OPEN, RequirementStatus.PARTIALLY_FILLED}:
                raise HTTPException(400, "Buyer requirement is not eligible.")
            if batch.crop_name.casefold() != requirement.crop_name.casefold():
                raise HTTPException(400, "Crop names do not match.")
            if payload.rejected_quantity_kg > batch.remaining_quantity_kg or payload.rejected_quantity_kg > requirement.remaining_requirement_kg:
                raise HTTPException(409, "Rejected quantity exceeds current available quantity.")
            record = BuyerRejection(produce_batch_id=batch_id, **payload.model_dump(), fingerprint=fingerprint)
            db.add(record)
            db.flush()
            db.refresh(record)
            record_event(db,batch,'BUYER_REJECTION_RECORDED','buyer_rejection',record.id,quantity=record.rejected_quantity_kg,timestamp=record.created_at,metadata={'reason':record.reason,'buyer_requirement_id':requirement.id,'notes':record.notes})
            result, reused = RejectionRead.model_validate(record), False
    return result, reused


def evaluate_readiness(db: Session, batch: ProduceBatch, rules=RULES, today=None):
    today = today or datetime.now(timezone(timedelta(hours=5, minutes=30))).date()
    failed = db.scalar(select(func.count()).select_from(MatchingAttempt).where(MatchingAttempt.produce_batch_id == batch.id, MatchingAttempt.outcome == 'NO_MATCH'))
    counts = dict(db.execute(select(BuyerRejection.reason, func.count()).where(BuyerRejection.produce_batch_id == batch.id).group_by(BuyerRejection.reason)).all())
    quality = counts.get('QUALITY_MISMATCH', 0)
    cosmetic = counts.get('COSMETIC_DEFECT', 0)
    risk = getattr(batch.risk_level, 'value', batch.risk_level)
    warnings, reasons = [], []
    days = (batch.available_until-today).days if batch.available_until else None
    if days is None:
        warnings.append('Availability deadline is missing; deadline urgency is unknown.')
    grade = (batch.quality_grade or '').upper()
    if grade not in {'A','B','C'}:
        warnings.append('Quality grade is missing or unrecognized; no downgrade inferred.')
    urgency = risk if risk in {'LOW','MEDIUM','HIGH','CRITICAL'} else 'LOW'
    if days is not None and days <= rules.urgent_deadline_days:
        urgency = 'CRITICAL' if days <= 0 else ('CRITICAL' if risk == 'CRITICAL' else 'HIGH')
        reasons.append('Availability deadline is due or approaching; this is not a food-safety assessment.')
    if risk in {'MEDIUM','HIGH','CRITICAL'}:
        reasons.append(f'Existing risk level is {risk}.')
    if quality or cosmetic:
        reasons.append(f'Recorded quality/cosmetic rejections: {quality}/{cosmetic}; buyer feedback does not establish food safety.')
    candidate = False
    available = batch.remaining_quantity_kg > 0 and batch.status not in {ProduceStatus.COMPLETED, ProduceStatus.CANCELLED, ProduceStatus.REROUTING}
    if available:
        if risk == 'CRITICAL':
            candidate = True
        if failed >= rules.failed_attempt_threshold:
            candidate = True
            reasons.append(f'{failed} genuine NO_MATCH attempts reached the review threshold.')
        if failed >= rules.combined_failure_threshold and (risk in {'HIGH','CRITICAL'} or (days is not None and days <= rules.urgent_deadline_days) or grade == 'C'):
            candidate = True
            reasons.append('Repeated unmatched attempts combine with urgency or documented grade C.')
        if failed >= 1 and quality+cosmetic >= rules.quality_rejection_threshold:
            candidate = True
            reasons.append('Unmatched inventory and repeated quality/cosmetic feedback warrant review.')
    else:
        reasons.append('No available primary inventory; no routing recommendation is activated.')
    action = 'REVIEW_FOR_ALTERNATIVE_ROUTING' if candidate else ('PRIORITIZE_PRIMARY_SALE' if available and (urgency != 'LOW' or quality+cosmetic > 0) else 'CONTINUE_PRIMARY_MATCHING')
    return dict(produce_batch_id=batch.id, remaining_quantity_kg=batch.remaining_quantity_kg, current_risk_level=risk, evaluated_urgency=urgency, failed_matching_attempts=failed, quality_rejections=quality, cosmetic_rejections=cosmetic, rerouting_candidate=candidate, reasons=reasons, warnings=warnings, recommended_action=action)
