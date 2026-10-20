from app.core.auth import get_authorized_db
from app.core.access import authorize_request, scope_query
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import ProduceBatch
from app.routes.common import get_or_404
from app.schemas.traceability import BatchTimeline
from app.services.traceability_service import timeline

router=APIRouter(dependencies=[Depends(authorize_request)], tags=['Batch Traceability'])


@router.get('/produce/{batch_id}/timeline',response_model=BatchTimeline)
def batch_timeline(batch_id:int,db:Session=Depends(get_authorized_db)):
    # Read lock keeps inventory and source records consistent with allocation writes.
    batch=db.scalar(select(ProduceBatch).where(ProduceBatch.id==batch_id).with_for_update(read=True))
    if batch is None:
        raise HTTPException(404,'Produce batch not found.')
    return timeline(db,batch)
