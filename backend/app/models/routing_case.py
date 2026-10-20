"""Routing-case records only; no alternative matching is implemented."""
from decimal import Decimal
from enum import Enum as PythonEnum
from typing import Any

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, Integer, JSON, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import TimestampMixin
from app.models.enums import RiskLevel


class RoutingCaseStatus(str, PythonEnum):
    AWAITING_ALTERNATIVE_MATCH = "AWAITING_ALTERNATIVE_MATCH"
    MATCHED = "MATCHED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class RoutingCase(TimestampMixin, Base):
    __tablename__ = "routing_cases"
    __table_args__ = (
        CheckConstraint("quantity_kg > 0", name="ck_routing_case_quantity_positive"),
        Index(
            "uq_routing_cases_active_batch", "produce_batch_id", unique=True,
            postgresql_where=text("status IN ('AWAITING_ALTERNATIVE_MATCH', 'MATCHED')"),
            sqlite_where=text("status IN ('AWAITING_ALTERNATIVE_MATCH', 'MATCHED')"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    produce_batch_id: Mapped[int] = mapped_column(ForeignKey("produce_batches.id"), index=True)
    quantity_kg: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    trigger_reason: Mapped[str] = mapped_column(String(255))
    # JSON variant supports isolated SQLite tests; PostgreSQL always uses JSONB.
    trigger_details: Mapped[dict[str, Any]] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), default=dict, nullable=False)
    risk_level_at_creation: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel, name="risk_level"))
    status: Mapped[RoutingCaseStatus] = mapped_column(
        Enum(RoutingCaseStatus, name="routing_case_status"),
        default=RoutingCaseStatus.AWAITING_ALTERNATIVE_MATCH,
        server_default="AWAITING_ALTERNATIVE_MATCH",
    )
    produce_batch: Mapped["ProduceBatch"] = relationship("ProduceBatch", foreign_keys=[produce_batch_id])
