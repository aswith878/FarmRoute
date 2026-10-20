from datetime import datetime
from sqlalchemy import Boolean, Enum, Integer, String, Text, DateTime, Index, text, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import LocationMixin, TimestampMixin
from app.models.enums import UserRole


class User(LocationMixin, TimestampMixin, Base):
    __tablename__ = "users"

    __table_args__ = (Index("uq_users_email_lower", text("lower(email)"), unique=True),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(50))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())

    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    produce_batches: Mapped[list["ProduceBatch"]] = relationship("ProduceBatch", back_populates="farmer", foreign_keys="ProduceBatch.farmer_id")
    buyer_requirements: Mapped[list["BuyerRequirement"]] = relationship("BuyerRequirement", back_populates="buyer", foreign_keys="BuyerRequirement.buyer_id")
    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="buyer", foreign_keys="Transaction.buyer_id")
