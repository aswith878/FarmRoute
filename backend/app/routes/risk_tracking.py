from app.core.auth import get_authorized_db
from app.core.access import authorize_request, scope_query
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import ProduceBatch
from app.routes.common import get_or_404
from app.schemas.risk_tracking import MatchingAttemptRead, RejectionCreate, RejectionRead, RoutingReadiness
from app.services.risk_service import record_matching_attempt, record_rejection, evaluate_readiness

router = APIRouter(dependencies=[Depends(authorize_request)], prefix='/produce', tags=['Risk and Rejection Tracking'])


@router.post('/{batch_id}/matching-attempts', response_model=MatchingAttemptRead, status_code=201)
def matching_attempt(batch_id: int, response: Response, db: Session = Depends(get_authorized_db)):
    record, reused = record_matching_attempt(db, batch_id)
    if reused:
        response.status_code = 200
    return record


@router.post('/{batch_id}/rejections', response_model=RejectionRead, status_code=201)
def rejection(batch_id: int, payload: RejectionCreate, response: Response, db: Session = Depends(get_authorized_db)):
    record, reused = record_rejection(db, batch_id, payload)
    if reused:
        response.status_code = 200
    return record


@router.get('/{batch_id}/routing-readiness', response_model=RoutingReadiness)
def readiness(batch_id: int, db: Session = Depends(get_authorized_db)):
    return evaluate_readiness(db, get_or_404(db, ProduceBatch, batch_id))
