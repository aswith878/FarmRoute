from app.core.auth import get_authorized_db
from app.core.access import authorize_request, scope_query
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import BuyerRequirement
from app.models.enums import RequirementStatus, UserRole
from app.routes.common import apply_update, get_or_404, require_owner, save
from app.schemas.buyer_requirement import BuyerRequirementCreate, BuyerRequirementRead, BuyerRequirementUpdate

router = APIRouter(dependencies=[Depends(authorize_request)], prefix="/buyer-requirements", tags=["Buyer Requirements"])


@router.post("", response_model=BuyerRequirementRead, status_code=201)
def create_requirement(payload: BuyerRequirementCreate, db: Session = Depends(get_authorized_db)):
    require_owner(db, payload.buyer_id, UserRole.BUYER)
    requirement = BuyerRequirement(**payload.model_dump(), remaining_requirement_kg=payload.required_quantity_kg, status=RequirementStatus.OPEN)
    return save(db, requirement)


@router.get("", response_model=list[BuyerRequirementRead])
def list_requirements(buyer_id: int | None = None, crop_name: str | None = None, status: RequirementStatus | None = None, db: Session = Depends(get_authorized_db)):
    query = select(BuyerRequirement).order_by(BuyerRequirement.id)
    for field, value in ((BuyerRequirement.buyer_id, buyer_id), (BuyerRequirement.crop_name, crop_name), (BuyerRequirement.status, status)):
        if value is not None:
            query = query.where(field == value)
    return db.scalars(scope_query(db, query, BuyerRequirement)).all()


@router.get("/{requirement_id}", response_model=BuyerRequirementRead)
def read_requirement(requirement_id: int, db: Session = Depends(get_authorized_db)):
    return get_or_404(db, BuyerRequirement, requirement_id)


@router.put("/{requirement_id}", response_model=BuyerRequirementRead)
def update_requirement(requirement_id: int, payload: BuyerRequirementUpdate, db: Session = Depends(get_authorized_db)):
    # Serialize updates so price range checks include any prior concurrent update.
    requirement = db.scalar(select(BuyerRequirement).where(BuyerRequirement.id == requirement_id).with_for_update())
    if requirement is None:
        raise HTTPException(status_code=404, detail="Record not found.")
    changes = payload.model_dump(exclude_unset=True)
    minimum = changes.get("minimum_price_per_kg", requirement.minimum_price_per_kg)
    maximum = changes.get("maximum_price_per_kg", requirement.maximum_price_per_kg)
    if maximum < minimum:
        raise HTTPException(status_code=422, detail="maximum_price_per_kg must be at least minimum_price_per_kg.")
    apply_update(requirement, payload)
    return save(db, requirement)


@router.post("/{requirement_id}/cancel", response_model=BuyerRequirementRead)
def cancel_requirement(requirement_id: int, db: Session = Depends(get_authorized_db)):
    requirement = db.scalar(
        select(BuyerRequirement).where(BuyerRequirement.id == requirement_id).with_for_update()
    )
    if requirement is None:
        raise HTTPException(status_code=404, detail="Record not found.")
    if requirement.status not in {RequirementStatus.OPEN, RequirementStatus.PARTIALLY_FILLED}:
        raise HTTPException(status_code=409, detail="Only an active requirement can be cancelled.")
    requirement.status = RequirementStatus.CANCELLED
    return save(db, requirement)
