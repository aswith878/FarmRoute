from app.core.auth import get_authorized_db
from app.core.access import authorize_request, scope_query
from typing import Annotated
from fastapi import APIRouter,Depends,Header,HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import ProcessorRequirement,User,RoutingCase,ProduceBatch,AlternativeAllocation
from app.models.enums import RequirementStatus, UserRole
from app.routes.common import get_or_404,save,apply_update
from app.schemas.processor import ProcessorRequirementCreate,ProcessorRequirementRead,ProcessorRequirementUpdate,ProcessorMatches,SuitabilityAssessmentRequest,AlternativeAcceptRequest,AlternativeAllocationRead
from app.services.processor_matching_service import find_processor_matches
from app.services.alternative_acceptance_service import record_suitability,accept_alternative

router=APIRouter(dependencies=[Depends(authorize_request)], tags=['Processor Requirements and Allocations'])


@router.post('/processor-requirements',response_model=ProcessorRequirementRead,status_code=201)
def create_requirement(payload:ProcessorRequirementCreate,db:Session=Depends(get_authorized_db)):
    processor=get_or_404(db,User,payload.processor_id)
    if processor.role!=UserRole.PROCESSOR or not processor.is_active:
        raise HTTPException(400,'Processor must be an active PROCESSOR user.')
    return save(db,ProcessorRequirement(**payload.model_dump(),remaining_requirement_kg=payload.required_quantity_kg))


@router.get('/processor-requirements',response_model=list[ProcessorRequirementRead])
def list_requirements(processor_id:int|None=None,db:Session=Depends(get_authorized_db)):
    query=select(ProcessorRequirement).order_by(ProcessorRequirement.id)
    if processor_id is not None:
        query=query.where(ProcessorRequirement.processor_id==processor_id)
    return db.scalars(scope_query(db, query, ProcessorRequirement)).all()


@router.get('/processor-requirements/{requirement_id}',response_model=ProcessorRequirementRead)
def read_requirement(requirement_id:int,db:Session=Depends(get_authorized_db)):
    return get_or_404(db,ProcessorRequirement,requirement_id)


@router.put('/processor-requirements/{requirement_id}',response_model=ProcessorRequirementRead)
def update_requirement(requirement_id:int,payload:ProcessorRequirementUpdate,db:Session=Depends(get_authorized_db)):
    requirement=db.scalar(select(ProcessorRequirement).where(ProcessorRequirement.id==requirement_id).with_for_update())
    if requirement is None:
        raise HTTPException(404,'Processor requirement not found.')
    changes=payload.model_dump(exclude_unset=True)
    if changes.get('maximum_price_per_kg',requirement.maximum_price_per_kg)<changes.get('minimum_price_per_kg',requirement.minimum_price_per_kg):
        raise HTTPException(422,'maximum_price_per_kg must be at least minimum_price_per_kg.')
    apply_update(requirement,payload)
    return save(db,requirement)


@router.post('/processor-requirements/{requirement_id}/cancel',response_model=ProcessorRequirementRead)
def cancel_requirement(requirement_id:int,db:Session=Depends(get_authorized_db)):
    requirement=db.scalar(select(ProcessorRequirement).where(ProcessorRequirement.id==requirement_id).with_for_update())
    if requirement is None:
        raise HTTPException(404,'Processor requirement not found.')
    if requirement.status not in {RequirementStatus.OPEN,RequirementStatus.PARTIALLY_FILLED}:
        raise HTTPException(409,'Only an active requirement can be cancelled.')
    requirement.status=RequirementStatus.CANCELLED
    return save(db,requirement)


@router.post('/routing-cases/{case_id}/suitability')
def assess(case_id:int,payload:SuitabilityAssessmentRequest,db:Session=Depends(get_authorized_db)):
    return record_suitability(db,case_id,payload)


@router.get('/routing-cases/{case_id}/processor-matches',response_model=ProcessorMatches)
def matches(case_id:int,db:Session=Depends(get_authorized_db)):
    case=get_or_404(db,RoutingCase,case_id)
    batch=get_or_404(db,ProduceBatch,case.produce_batch_id)
    result = find_processor_matches(db,case,batch)
    actor = db.info['actor']
    if actor.role == UserRole.PROCESSOR:
        result['matches'] = [row for row in result['matches'] if row['processor_id'] == actor.id]
    return result


@router.post('/routing-cases/{case_id}/accept',response_model=AlternativeAllocationRead)
def accept(case_id:int,payload:AlternativeAcceptRequest,idempotency_key:Annotated[str,Header(alias='Idempotency-Key',min_length=1,max_length=128)],db:Session=Depends(get_authorized_db)):
    if not idempotency_key.strip():
        raise HTTPException(422,'Idempotency-Key must not be blank.')
    return accept_alternative(db,case_id,payload,idempotency_key)


@router.get('/alternative-allocations',response_model=list[AlternativeAllocationRead])
def list_allocations(routing_case_id:int|None=None,db:Session=Depends(get_authorized_db)):
    query=select(AlternativeAllocation).order_by(AlternativeAllocation.id)
    if routing_case_id is not None:
        query=query.where(AlternativeAllocation.routing_case_id==routing_case_id)
    return db.scalars(scope_query(db, query, AlternativeAllocation)).all()


@router.get('/alternative-allocations/{allocation_id}',response_model=AlternativeAllocationRead)
def read_allocation(allocation_id:int,db:Session=Depends(get_authorized_db)):
    return get_or_404(db,AlternativeAllocation,allocation_id)
