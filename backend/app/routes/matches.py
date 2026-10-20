from app.core.auth import get_authorized_db
from app.core.access import authorize_request, scope_query
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import ProduceBatch
from app.routes.common import get_or_404
from app.schemas.matching import ProduceMatches
from app.services.matching_service import find_primary_matches

router = APIRouter(dependencies=[Depends(authorize_request)], prefix="/matches", tags=["Primary Matches"])


@router.get("/produce/{batch_id}", response_model=ProduceMatches)
def matches_for_produce(batch_id: int, db: Session = Depends(get_authorized_db)):
    return find_primary_matches(db, get_or_404(db, ProduceBatch, batch_id))
