from decimal import Decimal
from datetime import date
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.schemas.common import SchemaBase, ReadFields, Quantity, Price, UpdateBase
from app.models.enums import RequirementStatus


class ProcessorRequirementCreate(SchemaBase):
    processor_id: int = Field(gt=0)
    crop_name: str = Field(min_length=1,max_length=255)
    required_quantity_kg: Quantity
    minimum_acceptable_quality: str = Field(min_length=1,max_length=50)
    acceptable_produce_conditions: list[str] = Field(min_length=1,max_length=30)
    intended_utilization: str = Field(min_length=1,max_length=100)
    minimum_price_per_kg: Price
    maximum_price_per_kg: Price
    maximum_distance_km: Decimal | None = Field(default=None,ge=0,max_digits=10,decimal_places=2)
    pickup_date: date | None = None

    @field_validator('minimum_acceptable_quality','intended_utilization')
    @classmethod
    def normalize(cls,value):
        return value.strip().upper()

    @field_validator('acceptable_produce_conditions')
    @classmethod
    def normalize_conditions(cls,values):
        if any(not value.strip() or len(value.strip())>255 for value in values):
            raise ValueError('Conditions must be nonempty and at most 255 characters')
        return sorted(set(value.strip().upper() for value in values))

    @model_validator(mode='after')
    def prices(self):
        if self.maximum_price_per_kg < self.minimum_price_per_kg:
            raise ValueError('maximum_price_per_kg must be at least minimum_price_per_kg')
        return self


class ProcessorRequirementRead(ProcessorRequirementCreate,ReadFields):
    remaining_requirement_kg: Decimal
    status: RequirementStatus


class ProcessorRequirementUpdate(UpdateBase):
    minimum_acceptable_quality: str | None = Field(default=None,min_length=1,max_length=50)
    acceptable_produce_conditions: list[str] | None = Field(default=None,min_length=1,max_length=30)
    intended_utilization: str | None = Field(default=None,min_length=1,max_length=100)
    minimum_price_per_kg: Price | None = None
    maximum_price_per_kg: Price | None = None
    maximum_distance_km: Decimal | None = Field(default=None,ge=0,max_digits=10,decimal_places=2)
    pickup_date: date | None = None

    @model_validator(mode='after')
    def normalize(self):
        for key in ('minimum_acceptable_quality','acceptable_produce_conditions','intended_utilization'):
            if key in self.model_fields_set and getattr(self,key) is None:
                raise ValueError(f'{key} must not be null')
        for key in ('minimum_acceptable_quality','intended_utilization'):
            if getattr(self,key) is not None:
                setattr(self,key,getattr(self,key).strip().upper())
        if self.acceptable_produce_conditions is not None:
            self.acceptable_produce_conditions=ProcessorRequirementCreate.normalize_conditions(self.acceptable_produce_conditions)
        return self


class SuitabilityAssessmentRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    processor_requirement_id: int | None = Field(default=None, gt=0)
    intended_utilization: str = Field(min_length=1,max_length=100)
    confirmed_condition: str = Field(min_length=1,max_length=255)
    suitable: bool
    assessed_by: str = Field(min_length=1,max_length=255)
    assessment_notes: str = Field(min_length=1,max_length=4000)

    @field_validator('intended_utilization','confirmed_condition')
    @classmethod
    def normalize(cls,value):
        return value.upper()


class AlternativeAcceptRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    processor_requirement_id: int = Field(gt=0)
    accepted_quantity_kg: Quantity
    price_per_kg: Price | None = None


class AlternativeAllocationRead(ReadFields):
    model_config=ConfigDict(from_attributes=True)
    routing_case_id: int
    produce_batch_id: int
    processor_requirement_id: int
    processor_id: int
    quantity_kg: Decimal
    price_per_kg: Decimal | None
    intended_utilization: str
    status: str
    idempotency_key: str


class ProcessorMatch(BaseModel):
    processor_id: int
    processor_name: str
    processor_requirement_id: int
    compatible_quantity_kg: Decimal
    distance_km: float | None
    match_score: float
    score_breakdown: dict[str,float]
    suitability_explanation: str
    intended_utilization: str
    warnings: list[str]


class ProcessorMatches(BaseModel):
    routing_case_id: int
    available_quantity_kg: Decimal
    matches: list[ProcessorMatch]
    warnings: list[str]
