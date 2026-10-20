from datetime import date
from decimal import Decimal

from pydantic import Field

from app.models.enums import ProduceStatus, RiskLevel
from app.schemas.common import Price, Quantity, ReadFields, SchemaBase, UpdateBase


class ProduceBatchCreate(SchemaBase):
    farmer_id: int = Field(gt=0)
    crop_name: str = Field(min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=100)
    initial_quantity_kg: Quantity
    expected_price_per_kg: Price
    harvest_date: date
    available_until: date | None = None
    quality_grade: str = Field(min_length=1, max_length=50)
    risk_level: RiskLevel = RiskLevel.LOW
    storage_type: str | None = Field(default=None, max_length=100)
    visible_condition: str | None = None
    cosmetic_defects: str | None = None
    notes: str | None = None
    image_url: str | None = None


class ProduceBatchRead(ProduceBatchCreate, ReadFields):
    batch_code: str
    status: ProduceStatus
    sold_quantity_kg: Decimal
    remaining_quantity_kg: Decimal
    rerouted_quantity_kg: Decimal


class ProduceBatchUpdate(UpdateBase):
    expected_price_per_kg: Price | None = None
    available_until: date | None = None
    quality_grade: str | None = Field(default=None, min_length=1, max_length=50)
    risk_level: RiskLevel | None = None
    storage_type: str | None = Field(default=None, max_length=100)
    visible_condition: str | None = None
    cosmetic_defects: str | None = None
    notes: str | None = None
    image_url: str | None = None
