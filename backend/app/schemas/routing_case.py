from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.enums import RiskLevel
from app.models.routing_case import RoutingCaseStatus


class RoutingCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    produce_batch_id: int
    quantity_kg: Decimal
    trigger_reason: str
    trigger_details: dict[str, Any]
    risk_level_at_creation: RiskLevel
    status: RoutingCaseStatus
    created_at: datetime
    updated_at: datetime
