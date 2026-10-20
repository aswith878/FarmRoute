from datetime import date
from decimal import Decimal

from pydantic import Field, model_validator

from app.models.enums import RequirementStatus
from app.schemas.common import Price, Quantity, ReadFields, SchemaBase, UpdateBase


class BuyerRequirementCreate(SchemaBase):
    buyer_id: int = Field(gt=0)
    crop_name: str = Field(min_length=1, max_length=255)
    required_quantity_kg: Quantity
    minimum_quality: str = Field(min_length=1, max_length=50)
    minimum_price_per_kg: Price
    maximum_price_per_kg: Price
    maximum_distance_km: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    pickup_date: date | None = None

    @model_validator(mode="after")
    def validate_price_range(self):
        if self.maximum_price_per_kg < self.minimum_price_per_kg:
            raise ValueError("maximum_price_per_kg must be at least minimum_price_per_kg")
        return self


class BuyerRequirementRead(BuyerRequirementCreate, ReadFields):
    status: RequirementStatus
    remaining_requirement_kg: Decimal


class BuyerRequirementUpdate(UpdateBase):
    minimum_quality: str | None = Field(default=None, min_length=1, max_length=50)
    minimum_price_per_kg: Price | None = None
    maximum_price_per_kg: Price | None = None
    maximum_distance_km: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    pickup_date: date | None = None
