from datetime import datetime
from decimal import Decimal
from typing import Any
from pydantic import BaseModel


class TimelineEvent(BaseModel):
    event_id: int|str
    event_type: str
    description: str
    quantity_kg: Decimal|None
    timestamp: datetime
    related_entity: dict[str,Any]
    metadata: dict[str,Any]
    previous_status: str|None
    new_status: str|None
    history_origin: str


class BatchTimeline(BaseModel):
    batch_id: int
    batch_code: str
    crop_name: str
    initial_quantity_kg: Decimal
    sold_quantity_kg: Decimal
    remaining_quantity_kg: Decimal
    rerouted_quantity_kg: Decimal
    events: list[TimelineEvent]
