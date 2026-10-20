from datetime import date
from decimal import Decimal
from sqlalchemy import CheckConstraint, Date, Enum, ForeignKey, Integer, JSON, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.common import LocationMixin, TimestampMixin
from app.models.enums import RequirementStatus


class ProcessorRequirement(LocationMixin, TimestampMixin, Base):
    __tablename__ = 'processor_requirements'
    __table_args__ = (
        CheckConstraint('required_quantity_kg > 0 AND remaining_requirement_kg >= 0 AND remaining_requirement_kg <= required_quantity_kg', name='ck_processor_requirement_quantities'),
        CheckConstraint('minimum_price_per_kg >= 0 AND maximum_price_per_kg >= minimum_price_per_kg', name='ck_processor_requirement_prices'),
        CheckConstraint('maximum_distance_km >= 0', name='ck_processor_requirement_distance'),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    processor_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    crop_name: Mapped[str] = mapped_column(String(255))
    required_quantity_kg: Mapped[Decimal] = mapped_column(Numeric(14,3))
    remaining_requirement_kg: Mapped[Decimal] = mapped_column(Numeric(14,3), default=lambda context: context.get_current_parameters()['required_quantity_kg'])
    minimum_acceptable_quality: Mapped[str] = mapped_column(String(50))
    acceptable_produce_conditions: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    intended_utilization: Mapped[str] = mapped_column(String(100))
    minimum_price_per_kg: Mapped[Decimal] = mapped_column(Numeric(14,2))
    maximum_price_per_kg: Mapped[Decimal] = mapped_column(Numeric(14,2))
    maximum_distance_km: Mapped[Decimal | None] = mapped_column(Numeric(10,2))
    pickup_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[RequirementStatus] = mapped_column(Enum(RequirementStatus, name='requirement_status'), default=RequirementStatus.OPEN, server_default='OPEN')
    processor: Mapped['User'] = relationship('User', foreign_keys=[processor_id])
