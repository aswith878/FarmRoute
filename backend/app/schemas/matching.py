from decimal import Decimal
from pydantic import BaseModel


class ScoreBreakdown(BaseModel):
    crop: float
    quantity: float
    quality: float
    price: float
    distance: float
    pickup: float
    urgency: float


class BuyerMatch(BaseModel):
    buyer_requirement_id: int
    buyer_id: int
    buyer_name: str
    matchable_quantity_kg: Decimal
    remaining_buyer_requirement_kg: Decimal
    distance_km: float | None
    match_score: float
    score_breakdown: ScoreBreakdown
    warnings: list[str]


class ProduceMatches(BaseModel):
    produce_batch_id: int
    remaining_quantity_kg: Decimal
    matches: list[BuyerMatch]
