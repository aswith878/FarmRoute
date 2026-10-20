from datetime import datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.common import Quantity

RejectionReason = Literal['QUALITY_MISMATCH', 'COSMETIC_DEFECT', 'PRICE_DISAGREEMENT', 'PICKUP_UNAVAILABLE', 'QUANTITY_MISMATCH', 'OTHER']


class RejectionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    buyer_requirement_id: int = Field(gt=0)
    reason: RejectionReason
    rejected_quantity_kg: Quantity
    notes: str | None = Field(default=None, max_length=4000)


class MatchingAttemptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    produce_batch_id: int
    attempted_at: datetime
    matching_type: str
    compatible_buyers_found: int
    remaining_quantity_at_attempt: Decimal
    outcome: str
    created_at: datetime


class RejectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    produce_batch_id: int
    buyer_requirement_id: int
    reason: RejectionReason
    rejected_quantity_kg: Decimal
    notes: str | None
    created_at: datetime


class RoutingReadiness(BaseModel):
    produce_batch_id: int
    remaining_quantity_kg: Decimal
    current_risk_level: str
    evaluated_urgency: str
    failed_matching_attempts: int
    quality_rejections: int
    cosmetic_rejections: int
    rerouting_candidate: bool
    reasons: list[str]
    warnings: list[str]
    recommended_action: Literal['CONTINUE_PRIMARY_MATCHING', 'PRIORITIZE_PRIMARY_SALE', 'REVIEW_FOR_ALTERNATIVE_ROUTING']
