from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.transaction import TransactionStatus, TransactionType
from app.schemas.common import Price, Quantity, ReadFields


class TransactionAcceptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    produce_batch_id: int = Field(gt=0)
    buyer_requirement_id: int = Field(gt=0)
    quantity_kg: Quantity
    price_per_kg: Price | None = None


class TransactionRead(ReadFields):
    model_config = ConfigDict(from_attributes=True)
    produce_batch_id: int
    buyer_requirement_id: int
    buyer_id: int
    quantity_kg: Decimal
    price_per_kg: Decimal | None
    transaction_type: TransactionType
    status: TransactionStatus
