"""Manual primary-sale acceptance; no matching or rerouting."""
from app.core.auth import enforce_owner
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BuyerRequirement, ProduceBatch, Transaction, User
from app.models.enums import ProduceStatus, RequirementStatus, UserRole
from app.models.transaction import TransactionStatus, TransactionType
from app.schemas.transaction import TransactionAcceptRequest, TransactionRead
from app.services.traceability_service import record_event


def accept_transaction(db: Session, payload: TransactionAcceptRequest) -> TransactionRead:
    # This service owns the transaction; callers must supply a fresh session.
    # All acceptance requests lock produce first, then requirement, avoiding
    # inconsistent lock ordering and serializing overlapping inventory sales.
    with db.begin():
        batch = db.scalar(select(ProduceBatch).where(ProduceBatch.id == payload.produce_batch_id).with_for_update())
        if batch is None:
            raise HTTPException(status_code=404, detail="Produce batch not found.")
        requirement = db.scalar(select(BuyerRequirement).where(BuyerRequirement.id == payload.buyer_requirement_id).with_for_update())
        if requirement is None:
            raise HTTPException(status_code=404, detail="Buyer requirement not found.")
        enforce_owner(db.info.get('actor'), requirement.buyer_id, UserRole.BUYER)
        buyer = db.get(User, requirement.buyer_id)
        if buyer is None or buyer.role != UserRole.BUYER:
            raise HTTPException(status_code=400, detail="Requirement must belong to a BUYER.")
        if batch.status in {ProduceStatus.COMPLETED, ProduceStatus.CANCELLED, ProduceStatus.REROUTING}:
            raise HTTPException(status_code=409, detail="Produce batch is not available for primary sale.")
        if requirement.status in {RequirementStatus.FULFILLED, RequirementStatus.CANCELLED}:
            raise HTTPException(status_code=409, detail="Buyer requirement is not open for acceptance.")
        if batch.crop_name.casefold() != requirement.crop_name.casefold():
            raise HTTPException(status_code=400, detail="Crop names do not match.")
        if payload.quantity_kg > batch.remaining_quantity_kg:
            raise HTTPException(status_code=409, detail="Quantity exceeds remaining produce.")
        if payload.quantity_kg > requirement.remaining_requirement_kg:
            raise HTTPException(status_code=409, detail="Quantity exceeds remaining buyer requirement.")

        previous_status = batch.status
        batch.sold_quantity_kg += payload.quantity_kg
        batch.remaining_quantity_kg -= payload.quantity_kg
        requirement.remaining_requirement_kg -= payload.quantity_kg
        batch.status = ProduceStatus.PARTIALLY_SOLD if batch.remaining_quantity_kg > 0 else ProduceStatus.COMPLETED
        requirement.status = RequirementStatus.PARTIALLY_FILLED if requirement.remaining_requirement_kg > 0 else RequirementStatus.FULFILLED
        record = Transaction(
            produce_batch_id=batch.id, buyer_requirement_id=requirement.id,
            buyer_id=buyer.id, quantity_kg=payload.quantity_kg,
            price_per_kg=payload.price_per_kg, transaction_type=TransactionType.PRIMARY_SALE,
            status=TransactionStatus.ACCEPTED,
        )
        db.add(record)
        db.flush()
        db.refresh(record)
        record_event(db,batch,'PRIMARY_SALE_ACCEPTED','transaction',record.id,quantity=record.quantity_kg,timestamp=record.created_at,previous_status=previous_status,new_status=batch.status,metadata={'buyer_id':buyer.id,'buyer_requirement_id':requirement.id,'price_per_kg':record.price_per_kg})
        if batch.remaining_quantity_kg == 0:
            record_event(db,batch,'BATCH_FULLY_ALLOCATED','transaction',record.id,quantity=batch.initial_quantity_kg,timestamp=record.created_at,previous_status=previous_status,new_status=batch.status)
        # Validate/serialize before commit so a response-validation failure also
        # rolls back. The context commits only after all operations succeed.
        result = TransactionRead.model_validate(record)
    return result
