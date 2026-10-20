"""Atomic allocated quantities; does not imply physical delivery/utilization."""
import hashlib
import json
from datetime import datetime,timezone
from app.core.auth import enforce_owner
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import RoutingCase,ProduceBatch,ProcessorRequirement,User,AlternativeAllocation
from app.models.enums import RequirementStatus,ProduceStatus,UserRole
from app.models.routing_case import RoutingCaseStatus
from app.schemas.processor import AlternativeAllocationRead
from app.services.processor_matching_service import ACTIVE_CASE_STATUSES,available_case_quantity,compatibility
from app.services.traceability_service import record_event,suitability_suffix


def lock_case_and_batch(db,case_id):
    batch_id=db.scalar(select(RoutingCase.produce_batch_id).where(RoutingCase.id==case_id))
    if batch_id is None:
        raise HTTPException(404,'Routing case not found.')
    # Same first lock as primary acceptance and rerouting, preventing overselling.
    batch=db.scalar(select(ProduceBatch).where(ProduceBatch.id==batch_id).with_for_update().execution_options(populate_existing=True))
    case=db.scalar(select(RoutingCase).where(RoutingCase.id==case_id).with_for_update().execution_options(populate_existing=True))
    if batch is None or case is None:
        raise HTTPException(404,'Routing case or batch not found.')
    return case,batch


def record_suitability(db:Session,case_id,payload):
    with db.begin():
        case,batch=lock_case_and_batch(db,case_id)
        if case.status not in ACTIVE_CASE_STATUSES or batch.status in {ProduceStatus.COMPLETED,ProduceStatus.CANCELLED} or available_case_quantity(db,case,batch)<=0:
            raise HTTPException(409,'Routing case is not available for assessment.')
        if payload.confirmed_condition!=(batch.visible_condition or '').strip().upper():
            raise HTTPException(422,'Assessment must confirm the recorded produce condition.')
        actor=db.info.get('actor')
        assessment_key=payload.intended_utilization
        assessment_map='processing_suitability'
        if payload.processor_requirement_id is not None:
            requirement=db.scalar(select(ProcessorRequirement).where(ProcessorRequirement.id==payload.processor_requirement_id).with_for_update())
            if requirement is None:
                raise HTTPException(404,'Processor requirement not found.')
            enforce_owner(actor,requirement.processor_id,UserRole.PROCESSOR)
            if requirement.intended_utilization!=payload.intended_utilization or requirement.crop_name.casefold()!=batch.crop_name.casefold() or payload.confirmed_condition not in requirement.acceptable_produce_conditions or requirement.status not in {RequirementStatus.OPEN,RequirementStatus.PARTIALLY_FILLED} or requirement.remaining_requirement_kg<=0:
                raise HTTPException(409,'Assessment is incompatible with this requirement.')
            assessment_map='processing_suitability_by_requirement'
            assessment_key=str(requirement.id)
        elif actor is not None and actor.role!=UserRole.ADMIN:
            raise HTTPException(422,'processor_requirement_id is required.')
        previous=(case.trigger_details or {}).get(assessment_map,{}).get(assessment_key)
        declaration=payload.model_dump(exclude_none=True) | dict(crop_name=batch.crop_name,quality_grade=batch.quality_grade,risk_level=getattr(batch.risk_level,'value',batch.risk_level))
        if actor is not None:
            declaration['assessed_by']=actor.name
            declaration['assessor_user_id']=actor.id
        if isinstance(previous,dict) and all(previous.get(key)==value for key,value in declaration.items()):
            return previous  # Same decision retry: preserve timestamp and avoid duplicate event.
        # Preserve retained legacy evidence before replacing its JSON snapshot.
        if isinstance(previous,dict) and previous.get('assessed_at') and previous.get('intended_utilization'):
            try:
                previous_time=datetime.fromisoformat(previous['assessed_at'])
            except (ValueError,TypeError):
                previous_time=None
            if previous_time is not None:
                record_event(db,batch,'PROCESSOR_SUITABILITY_RECORDED','routing_case',case.id,timestamp=previous_time,metadata=previous,suffix=suitability_suffix(previous))
        assessment=declaration | dict(assessed_at=datetime.now(timezone.utc).isoformat())
        details=dict(case.trigger_details)
        assessments=dict(details.get(assessment_map,{}))
        assessments[assessment_key]=assessment
        details[assessment_map]=assessments
        case.trigger_details=details
        db.flush()
        record_event(db,batch,'PROCESSOR_SUITABILITY_RECORDED','routing_case',case.id,timestamp=datetime.fromisoformat(assessment['assessed_at']),metadata=assessment,suffix=suitability_suffix(assessment))
    return assessment


def accept_alternative(db:Session,case_id,payload,idempotency_key):
    # Required stable key: a retry after successful completion returns its record.
    normalized=[payload.processor_requirement_id,format(payload.accepted_quantity_kg.normalize(),'f'),None if payload.price_per_kg is None else format(payload.price_per_kg.normalize(),'f')]
    fingerprint=hashlib.sha256(json.dumps(normalized).encode()).hexdigest()
    with db.begin():
        case,batch=lock_case_and_batch(db,case_id)
        previous=db.scalar(select(AlternativeAllocation).where(AlternativeAllocation.routing_case_id==case_id,AlternativeAllocation.idempotency_key==idempotency_key))
        if previous:
            enforce_owner(db.info.get('actor'),previous.processor_id,UserRole.PROCESSOR)
            if previous.request_fingerprint!=fingerprint:
                raise HTTPException(409,'Idempotency key was already used for a different request.')
            return AlternativeAllocationRead.model_validate(previous)
        if case.status not in ACTIVE_CASE_STATUSES or batch.status in {ProduceStatus.COMPLETED,ProduceStatus.CANCELLED}:
            raise HTTPException(409,'Routing case or batch is not active.')
        available=available_case_quantity(db,case,batch)
        if available<=0:
            raise HTTPException(409,'Routing case is stale or has no available quantity.')
        requirement=db.scalar(select(ProcessorRequirement).where(ProcessorRequirement.id==payload.processor_requirement_id).with_for_update())
        if requirement is None:
            raise HTTPException(404,'Processor requirement not found.')
        enforce_owner(db.info.get('actor'),requirement.processor_id,UserRole.PROCESSOR)
        processor=db.get(User,requirement.processor_id)
        if processor is None or compatibility(case,batch,requirement,processor,available) is None:
            raise HTTPException(409,'Processor, crop, condition, suitability, quality, price, or pickup is incompatible.')
        if payload.price_per_kg is not None and not requirement.minimum_price_per_kg <= payload.price_per_kg <= requirement.maximum_price_per_kg:
            raise HTTPException(409,'Agreed price is outside the processor price range.')
        quantity=payload.accepted_quantity_kg
        if quantity>available or quantity>requirement.remaining_requirement_kg:
            raise HTTPException(409,'Quantity exceeds batch, routing-case, or processor availability.')
        if batch.initial_quantity_kg!=batch.sold_quantity_kg+batch.rerouted_quantity_kg+batch.remaining_quantity_kg:
            raise HTTPException(409,'Inventory balances are inconsistent; manual review is required.')
        previous_status=batch.status
        batch.remaining_quantity_kg-=quantity
        batch.rerouted_quantity_kg+=quantity
        requirement.remaining_requirement_kg-=quantity
        requirement.status=RequirementStatus.FULFILLED if requirement.remaining_requirement_kg==0 else RequirementStatus.PARTIALLY_FILLED
        if batch.remaining_quantity_kg==0:
            batch.status=ProduceStatus.COMPLETED
        case.status=RoutingCaseStatus.COMPLETED if available-quantity==0 else RoutingCaseStatus.MATCHED
        allocation=AlternativeAllocation(routing_case_id=case.id,produce_batch_id=batch.id,processor_requirement_id=requirement.id,processor_id=processor.id,quantity_kg=quantity,price_per_kg=payload.price_per_kg,intended_utilization=requirement.intended_utilization,status='ACCEPTED_ALLOCATED',idempotency_key=idempotency_key,request_fingerprint=fingerprint)
        db.add(allocation)
        db.flush()
        db.refresh(allocation)
        record_event(db,batch,'ALTERNATIVE_ALLOCATION_ACCEPTED','alternative_allocation',allocation.id,quantity=allocation.quantity_kg,timestamp=allocation.created_at,previous_status=previous_status,new_status=batch.status,metadata={'processor_id':processor.id,'processor_requirement_id':requirement.id,'routing_case_id':case.id,'price_per_kg':allocation.price_per_kg,'intended_utilization':allocation.intended_utilization,'status':allocation.status})
        if batch.remaining_quantity_kg==0:
            record_event(db,batch,'BATCH_FULLY_ALLOCATED','alternative_allocation',allocation.id,quantity=batch.initial_quantity_kg,timestamp=allocation.created_at,previous_status=previous_status,new_status=batch.status)
        result=AlternativeAllocationRead.model_validate(allocation)
    return result
