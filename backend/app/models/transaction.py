from decimal import Decimal
from enum import Enum as PythonEnum

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import TimestampMixin


class TransactionType(str, PythonEnum):
    PRIMARY_SALE = "PRIMARY_SALE"


class TransactionStatus(str, PythonEnum):
    ACCEPTED = "ACCEPTED"


class Transaction(TimestampMixin, Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("quantity_kg > 0", name="ck_transaction_quantity_positive"),
        CheckConstraint("price_per_kg >= 0", name="ck_transaction_price_nonnegative"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    produce_batch_id: Mapped[int] = mapped_column(ForeignKey("produce_batches.id"), index=True)
    buyer_requirement_id: Mapped[int] = mapped_column(ForeignKey("buyer_requirements.id"), index=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    quantity_kg: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    price_per_kg: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    transaction_type: Mapped[TransactionType] = mapped_column(Enum(TransactionType, name="transaction_type"))
    status: Mapped[TransactionStatus] = mapped_column(Enum(TransactionStatus, name="transaction_status"))
    produce_batch: Mapped["ProduceBatch"] = relationship("ProduceBatch", back_populates="transactions", foreign_keys=[produce_batch_id])
    buyer_requirement: Mapped["BuyerRequirement"] = relationship("BuyerRequirement", back_populates="transactions", foreign_keys=[buyer_requirement_id])
    buyer: Mapped["User"] = relationship("User", back_populates="transactions", foreign_keys=[buyer_id])
