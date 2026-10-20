from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import LocationMixin, TimestampMixin
from app.models.enums import RequirementStatus


class BuyerRequirement(LocationMixin, TimestampMixin, Base):
    __tablename__ = "buyer_requirements"
    __table_args__ = (
        CheckConstraint("required_quantity_kg > 0", name="ck_requirement_quantity_positive"),
        CheckConstraint("remaining_requirement_kg >= 0", name="ck_requirement_remaining_nonnegative"),
        CheckConstraint("minimum_price_per_kg >= 0 AND maximum_price_per_kg >= 0", name="ck_requirement_prices_nonnegative"),
        CheckConstraint("maximum_price_per_kg >= minimum_price_per_kg", name="ck_requirement_price_order"),
        CheckConstraint("maximum_distance_km >= 0", name="ck_requirement_distance_nonnegative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    crop_name: Mapped[str] = mapped_column(String(255))
    required_quantity_kg: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    remaining_requirement_kg: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=lambda context: context.get_current_parameters()["required_quantity_kg"])
    minimum_quality: Mapped[str] = mapped_column(String(50))
    minimum_price_per_kg: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    maximum_price_per_kg: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    maximum_distance_km: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    pickup_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[RequirementStatus] = mapped_column(Enum(RequirementStatus, name="requirement_status"), default=RequirementStatus.OPEN, server_default="OPEN")
    buyer: Mapped["User"] = relationship("User", back_populates="buyer_requirements", foreign_keys=[buyer_id])
    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="buyer_requirement", foreign_keys="Transaction.buyer_requirement_id")
