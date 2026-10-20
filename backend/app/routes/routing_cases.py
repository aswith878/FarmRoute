from app.core.auth import get_authorized_db
from app.core.access import authorize_request, scope_query, safe_case
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import RoutingCase
from app.routes.common import get_or_404
from app.schemas.routing_case import RoutingCaseRead
from app.services.rerouting_service import request_rerouting

router = APIRouter(dependencies=[Depends(authorize_request)], tags=['Routing Cases'])


@router.post('/produce/{batch_id}/rerouting', response_model=RoutingCaseRead)
def request_case(batch_id: int, db: Session = Depends(get_authorized_db)):
    # The service checks eligibility, owns the transaction, and reuses active cases.
    return request_rerouting(db, batch_id)


@router.get('/routing-cases', response_model=list[RoutingCaseRead])
def list_cases(db: Session = Depends(get_authorized_db)):
    return [safe_case(db,case) for case in db.scalars(scope_query(db, select(RoutingCase).order_by(RoutingCase.id), RoutingCase)).all()]


@router.get('/routing-cases/{case_id}', response_model=RoutingCaseRead)
def read_case(case_id: int, db: Session = Depends(get_authorized_db)):
    return safe_case(db,get_or_404(db, RoutingCase, case_id))
