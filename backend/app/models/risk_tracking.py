from datetime import datetime
from decimal import Decimal
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class MatchingAttempt(Base):
    __tablename__ = "matching_attempts"
    __table_args__ = (CheckConstraint("compatible_buyers_found >= 0 AND remaining_quantity_at_attempt > 0", name="ck_attempt_quantities"), CheckConstraint("matching_type = 'PRIMARY'", name="ck_attempt_type"), CheckConstraint("outcome IN ('MATCHES_FOUND', 'NO_MATCH')", name="ck_attempt_outcome"))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    produce_batch_id: Mapped[int] = mapped_column(ForeignKey("produce_batches.id"), index=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    matching_type: Mapped[str] = mapped_column(String(20), default="PRIMARY")
    compatible_buyers_found: Mapped[int] = mapped_column(Integer)
    remaining_quantity_at_attempt: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    outcome: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    produce_batch: Mapped["ProduceBatch"] = relationship("ProduceBatch", foreign_keys=[produce_batch_id])


class BuyerRejection(Base):
    __tablename__ = "buyer_rejections"
    __table_args__ = (CheckConstraint("rejected_quantity_kg > 0", name="ck_rejection_quantity"), CheckConstraint("reason IN ('QUALITY_MISMATCH','COSMETIC_DEFECT','PRICE_DISAGREEMENT','PICKUP_UNAVAILABLE','QUANTITY_MISMATCH','OTHER')", name="ck_rejection_reason"), UniqueConstraint("fingerprint", name="uq_rejection_fingerprint"))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    produce_batch_id: Mapped[int] = mapped_column(ForeignKey("produce_batches.id"), index=True)
    buyer_requirement_id: Mapped[int] = mapped_column(ForeignKey("buyer_requirements.id"), index=True)
    reason: Mapped[str] = mapped_column(String(30))
    rejected_quantity_kg: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    notes: Mapped[str | None] = mapped_column(Text)
    fingerprint: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    produce_batch: Mapped["ProduceBatch"] = relationship("ProduceBatch", foreign_keys=[produce_batch_id])
    buyer_requirement: Mapped["BuyerRequirement"] = relationship("BuyerRequirement", foreign_keys=[buyer_requirement_id])
