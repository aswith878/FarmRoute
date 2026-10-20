"""Shared CRUD database helpers; never expose driver error details."""
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import User


def get_or_404(db: Session, model, record_id: int):
    record = db.get(model, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Record not found.")
    return record


def require_owner(db: Session, user_id: int, role):
    user = get_or_404(db, User, user_id)
    if user.role != role:
        raise HTTPException(status_code=400, detail=f"User must have role {role.value}.")
    return user


def save(db: Session, record, conflict_message="Record conflicts with existing data.", before_commit=None):
    try:
        db.add(record)
        if before_commit is not None:
            db.flush()
            before_commit(db,record)
        db.commit()
        db.refresh(record)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=conflict_message) from None
    return record


def apply_update(record, payload):
    for name, value in payload.model_dump(exclude_unset=True).items():
        setattr(record, name, value)
