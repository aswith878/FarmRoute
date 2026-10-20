from app.core.auth import get_authorized_db
from app.core.access import authorize_request, scope_query
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Transaction
from app.routes.common import get_or_404
from app.schemas.transaction import TransactionAcceptRequest, TransactionRead
from app.services.transactions import accept_transaction

router = APIRouter(dependencies=[Depends(authorize_request)], prefix="/transactions", tags=["Transactions"])


@router.post("/accept", response_model=TransactionRead, status_code=201)
def accept(payload: TransactionAcceptRequest, db: Session = Depends(get_authorized_db)):
    return accept_transaction(db, payload)


@router.get("", response_model=list[TransactionRead])
def list_transactions(produce_batch_id: int | None = None, buyer_id: int | None = None, db: Session = Depends(get_authorized_db)):
    query = select(Transaction).order_by(Transaction.id)
    if produce_batch_id is not None:
        query = query.where(Transaction.produce_batch_id == produce_batch_id)
    if buyer_id is not None:
        query = query.where(Transaction.buyer_id == buyer_id)
    return db.scalars(scope_query(db, query, Transaction)).all()


@router.get("/{transaction_id}", response_model=TransactionRead)
def read_transaction(transaction_id: int, db: Session = Depends(get_authorized_db)):
    return get_or_404(db, Transaction, transaction_id)
