"""Deterministic primary buyer recommendations; never changes inventory."""
from datetime import datetime, timedelta, timezone
from math import asin, cos, radians, sin, sqrt, isfinite

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import BuyerRequirement, ProduceBatch, User
from app.models.enums import ProduceStatus, RequirementStatus, UserRole

WEIGHTS = {"crop": 10, "quantity": 20, "quality": 20, "price": 20, "distance": 10, "pickup": 10, "urgency": 10}
GRADES = {"A": 3, "B": 2, "C": 1}
RISK_INTENSITY = {"LOW": 0, "MEDIUM": 0.25, "HIGH": 0.65, "CRITICAL": 1}
NEUTRAL_SCORE = 50
MAX_PRICE_DEVIATION = 0.25
EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1, lon1, lat2, lon2):
    values = (lat1, lon1, lat2, lon2)
    if any(value is None for value in values):
        return None
    values = tuple(float(value) for value in values)
    if not all(isfinite(value) for value in values) or not (-90 <= values[0] <= 90 and -90 <= values[2] <= 90 and -180 <= values[1] <= 180 and -180 <= values[3] <= 180):
        return None
    a, b, c, d = map(radians, values)
    h = sin((c-a)/2)**2 + cos(a)*cos(c)*sin((d-b)/2)**2
    return EARTH_RADIUS_KM * 2 * asin(sqrt(max(0, min(1, h))))


def score_requirement(batch, requirement, buyer, today=None):
    today = today or datetime.now(timezone(timedelta(hours=5, minutes=30))).date()
    if batch.crop_name.casefold() != requirement.crop_name.casefold():
        return None
    if batch.remaining_quantity_kg <= 0 or requirement.remaining_requirement_kg <= 0:
        return None
    warnings = []
    grade = GRADES.get((batch.quality_grade or "").upper())
    minimum = GRADES.get((requirement.minimum_quality or "").upper())
    if grade is not None and minimum is not None and grade < minimum:
        return None
    quality = 100 if grade is not None and minimum is not None else NEUTRAL_SCORE
    if quality == NEUTRAL_SCORE:
        warnings.append("Quality grade unavailable or unrecognized; compatibility needs confirmation.")

    price = NEUTRAL_SCORE
    expected, low, high = batch.expected_price_per_kg, requirement.minimum_price_per_kg, requirement.maximum_price_per_kg
    if expected is not None and low is not None and high is not None:
        if low <= expected <= high:
            price = 100
        else:
            bound = low if expected < low else high
            deviation = float(abs(expected-bound) / max(abs(bound), 1))
            if deviation > MAX_PRICE_DEVIATION:
                return None
            price = 100 * (1-deviation/MAX_PRICE_DEVIATION)
    else:
        warnings.append("Price information unavailable; agreement needs confirmation.")

    distance = haversine_km(batch.latitude, batch.longitude, requirement.latitude, requirement.longitude)
    distance_score = NEUTRAL_SCORE
    limit = requirement.maximum_distance_km
    if distance is None:
        warnings.append("Coordinates unavailable; distance not verified.")
    elif limit is not None:
        limit = float(limit)
        if distance > limit:
            return None
        distance_score = 100 if limit == 0 else 100 - 50 * distance/limit
    else:
        distance_score = max(0, 100-distance)

    pickup = requirement.pickup_date
    earliest = max(today, batch.harvest_date) if batch.harvest_date else today
    if batch.available_until and batch.available_until < earliest:
        return None
    pickup_score = NEUTRAL_SCORE
    quickness = NEUTRAL_SCORE
    if pickup:
        if pickup < earliest or (batch.available_until and pickup > batch.available_until):
            return None
        quickness = max(0, 100-10*(pickup-earliest).days)
        pickup_score = quickness if batch.available_until else NEUTRAL_SCORE
    else:
        warnings.append("Pickup date unavailable; timing needs confirmation.")
    matchable = min(batch.remaining_quantity_kg, requirement.remaining_requirement_kg)
    quantity = 100 * float(matchable/batch.remaining_quantity_kg)
    compatibility = (quality + price + distance_score)/3
    risk = getattr(batch.risk_level, "value", batch.risk_level)
    intensity = RISK_INTENSITY.get(risk, 0)
    urgency = (1-intensity)*NEUTRAL_SCORE + intensity*(quickness*compatibility/100)
    scores = {"crop": 100, "quantity": quantity, "quality": quality, "price": price, "distance": distance_score, "pickup": pickup_score, "urgency": urgency}
    return {
        "buyer_requirement_id": requirement.id, "buyer_id": buyer.id, "buyer_name": buyer.name,
        "matchable_quantity_kg": matchable, "remaining_buyer_requirement_kg": requirement.remaining_requirement_kg,
        "distance_km": round(distance, 3) if distance is not None else None,
        "match_score": round(sum(scores[key]*weight for key, weight in WEIGHTS.items())/100, 2),
        "score_breakdown": {key: round(value, 2) for key, value in scores.items()},
        "warnings": warnings,
    }


def find_primary_matches(db: Session, batch: ProduceBatch):
    result = {"produce_batch_id": batch.id, "remaining_quantity_kg": batch.remaining_quantity_kg, "matches": []}
    if batch.remaining_quantity_kg <= 0 or batch.status in {ProduceStatus.COMPLETED, ProduceStatus.CANCELLED, ProduceStatus.REROUTING}:
        return result
    candidates = db.execute(select(BuyerRequirement, User).join(User, BuyerRequirement.buyer_id == User.id).where(
        BuyerRequirement.status.in_([RequirementStatus.OPEN, RequirementStatus.PARTIALLY_FILLED]),
        BuyerRequirement.remaining_requirement_kg > 0,
        User.role == UserRole.BUYER, User.is_active.is_(True),
        func.lower(BuyerRequirement.crop_name) == batch.crop_name.lower(),
    )).all()
    for requirement, buyer in candidates:
        match = score_requirement(batch, requirement, buyer)
        if match is not None:
            result["matches"].append(match)
    result["matches"].sort(key=lambda match: (-match["match_score"], match["buyer_requirement_id"]))
    return result
