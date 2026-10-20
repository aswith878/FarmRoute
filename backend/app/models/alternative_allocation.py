from decimal import Decimal
from sqlalchemy import CheckConstraint, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.common import TimestampMixin


class AlternativeAllocation(TimestampMixin, Base):
    __tablename__ = 'alternative_allocations'
    __table_args__ = (
        CheckConstraint('quantity_kg > 0', name='ck_alternative_quantity'),
        CheckConstraint('price_per_kg >= 0', name='ck_alternative_price'),
        CheckConstraint("status = 'ACCEPTED_ALLOCATED'", name='ck_alternative_status'),
        UniqueConstraint('routing_case_id', 'idempotency_key', name='uq_alternative_idempotency'),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    routing_case_id: Mapped[int] = mapped_column(ForeignKey('routing_cases.id'), index=True)
    produce_batch_id: Mapped[int] = mapped_column(ForeignKey('produce_batches.id'), index=True)
    processor_requirement_id: Mapped[int] = mapped_column(ForeignKey('processor_requirements.id'), index=True)
    processor_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    quantity_kg: Mapped[Decimal] = mapped_column(Numeric(14,3))
    price_per_kg: Mapped[Decimal | None] = mapped_column(Numeric(14,2))
    intended_utilization: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30), default='ACCEPTED_ALLOCATED', server_default='ACCEPTED_ALLOCATED')
    idempotency_key: Mapped[str] = mapped_column(String(128))
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    routing_case: Mapped['RoutingCase'] = relationship('RoutingCase', foreign_keys=[routing_case_id])
    produce_batch: Mapped['ProduceBatch'] = relationship('ProduceBatch', foreign_keys=[produce_batch_id])
    processor_requirement: Mapped['ProcessorRequirement'] = relationship('ProcessorRequirement', foreign_keys=[processor_requirement_id])
    processor: Mapped['User'] = relationship('User', foreign_keys=[processor_id])
