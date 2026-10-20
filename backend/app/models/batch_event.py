from datetime import datetime
from decimal import Decimal
from typing import Any
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint, event, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class BatchEvent(Base):
    __tablename__='batch_events'
    __table_args__=(UniqueConstraint('event_key',name='uq_batch_event_key'),)
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    produce_batch_id: Mapped[int]=mapped_column(ForeignKey('produce_batches.id'),index=True)
    event_type: Mapped[str]=mapped_column(String(60),index=True)
    event_description: Mapped[str]=mapped_column(Text)
    quantity_kg: Mapped[Decimal|None]=mapped_column(Numeric(14,3))
    previous_status: Mapped[str|None]=mapped_column(String(50))
    new_status: Mapped[str|None]=mapped_column(String(50))
    related_entity_type: Mapped[str|None]=mapped_column(String(60))
    related_entity_id: Mapped[int|None]=mapped_column(Integer)
    event_metadata: Mapped[dict[str,Any]]=mapped_column('metadata',JSON().with_variant(JSONB(),'postgresql'),default=dict,nullable=False)
    event_key: Mapped[str]=mapped_column(String(200))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),index=True)


@event.listens_for(BatchEvent,'before_update')
@event.listens_for(BatchEvent,'before_delete')
def prevent_event_mutation(mapper,connection,target):
    raise ValueError('Batch events are append-only.')
