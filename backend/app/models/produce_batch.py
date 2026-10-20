from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, Enum, ForeignKey, Integer, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import LocationMixin, TimestampMixin
from app.models.enums import ProduceStatus, RiskLevel


class ProduceBatch(LocationMixin, TimestampMixin, Base):
    __tablename__ = "produce_batches"
    __table_args__ = (
        CheckConstraint("initial_quantity_kg > 0", name="ck_produce_initial_positive"),
        CheckConstraint("sold_quantity_kg >= 0 AND remaining_quantity_kg >= 0 AND rerouted_quantity_kg >= 0", name="ck_produce_balances_nonnegative"),
        CheckConstraint("expected_price_per_kg >= 0", name="ck_produce_price_nonnegative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_code: Mapped[str] = mapped_column(String(100), unique=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    crop_name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str | None] = mapped_column(String(100))
    initial_quantity_kg: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    sold_quantity_kg: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=Decimal("0"), server_default=text("0"))
    remaining_quantity_kg: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=lambda context: context.get_current_parameters()["initial_quantity_kg"])
    rerouted_quantity_kg: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=Decimal("0"), server_default=text("0"))
    expected_price_per_kg: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    harvest_date: Mapped[date] = mapped_column(Date)
    available_until: Mapped[date | None] = mapped_column(Date)
    quality_grade: Mapped[str] = mapped_column(String(50))
    risk_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel, name="risk_level"), default=RiskLevel.LOW, server_default="LOW")
    storage_type: Mapped[str | None] = mapped_column(String(100))
    visible_condition: Mapped[str | None] = mapped_column(Text)
    cosmetic_defects: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ProduceStatus] = mapped_column(Enum(ProduceStatus, name="produce_status"), default=ProduceStatus.ACTIVE, server_default="ACTIVE")
    farmer: Mapped["User"] = relationship("User", back_populates="produce_batches", foreign_keys=[farmer_id])
    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="produce_batch", foreign_keys="Transaction.produce_batch_id")
