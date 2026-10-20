from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

Quantity = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=3)]
Price = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)]


class SchemaBase(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True, str_strip_whitespace=True)
    location_name: str | None = Field(default=None, max_length=255)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90, decimal_places=6)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180, decimal_places=6)


class ReadFields(BaseModel):
    id: int
    created_at: datetime
    updated_at: datetime


class UpdateBase(SchemaBase):
    @model_validator(mode="after")
    def reject_required_nulls(self):
        required = {"name", "is_active", "expected_price_per_kg", "quality_grade", "risk_level", "minimum_quality", "minimum_price_per_kg", "maximum_price_per_kg"}
        for field in self.model_fields_set & required:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self
