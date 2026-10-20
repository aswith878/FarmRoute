"""Atomic append-only events plus deduplicated, read-only legacy history."""
import hashlib
from datetime import datetime,timezone
from decimal import Decimal
from enum import Enum
from sqlalchemy import select
from app.models import BatchEvent,Transaction,MatchingAttempt,BuyerRejection,RoutingCase,AlternativeAllocation

DESCRIPTIONS={
    'BATCH_CREATED':'Produce batch created.',
    'PRIMARY_MATCH_ATTEMPTED':'Explicit primary matching attempt recorded.',
    'PRIMARY_SALE_ACCEPTED':'Primary sale accepted; physical delivery is not confirmed.',
    'BUYER_REJECTION_RECORDED':'Buyer rejection recorded without inventory movement.',
    'RISK_REVIEWED':'Routing readiness reviewed during case initiation.',
    'ROUTING_CASE_CREATED':'Routing case initiated; inventory is not moved.',
    'PROCESSOR_SUITABILITY_RECORDED':'Explicit processing suitability assessment recorded, not a food-safety prediction.',
    'ALTERNATIVE_ALLOCATION_ACCEPTED':'Alternative quantity accepted and allocated; delivery/utilization is not confirmed.',
    'BATCH_FULLY_ALLOCATED':'All batch inventory is allocated; physical utilization is not confirmed.',
}


def json_safe(value):
    if isinstance(value,Decimal):
        return str(value)
    if isinstance(value,datetime):
        return value.isoformat()
    if isinstance(value,Enum):
        return value.value
    if isinstance(value,dict):
        return {key:json_safe(item) for key,item in value.items()}
    if isinstance(value,(list,tuple)):
        return [json_safe(item) for item in value]
    return value


def action_key(event_type,entity_type,entity_id,suffix=''):
    return f'{event_type}:{entity_type}:{entity_id}' + (':'+suffix if suffix else '')


def record_event(db,batch,event_type,entity_type,entity_id,*,quantity=None,metadata=None,timestamp=None,previous_status=None,new_status=None,suffix=''):
    """Never commits: the calling business transaction owns atomic persistence."""
    key=action_key(event_type,entity_type,entity_id,suffix)
    existing=db.scalar(select(BatchEvent).where(BatchEvent.event_key==key))
    if existing:
        return existing
    event=BatchEvent(produce_batch_id=batch.id,event_type=event_type,event_description=DESCRIPTIONS[event_type],quantity_kg=quantity,previous_status=json_safe(previous_status),new_status=json_safe(new_status),related_entity_type=entity_type,related_entity_id=entity_id,event_metadata=json_safe(metadata or {}),event_key=key)
    if timestamp is not None:
        event.created_at=timestamp
    db.add(event)
    db.flush()
    return event


def suitability_suffix(assessment):
    return hashlib.sha256((assessment['intended_utilization']+':'+assessment['assessed_at']).encode()).hexdigest()


def utc(timestamp):
    return timestamp.replace(tzinfo=timezone.utc) if timestamp.tzinfo is None else timestamp.astimezone(timezone.utc)


def timeline(db,batch):
    events={}
    recorded=db.scalars(select(BatchEvent).where(BatchEvent.produce_batch_id==batch.id)).all()
    def add(event_type,entity_type,entity_id,timestamp,quantity=None,metadata=None,suffix=''):
        key=action_key(event_type,entity_type,entity_id,suffix)
        events[key]=dict(event_id='historical:'+key,event_type=event_type,description=DESCRIPTIONS[event_type],quantity_kg=quantity,timestamp=utc(timestamp),related_entity={'type':entity_type,'id':entity_id},metadata=json_safe(metadata or {}),previous_status=None,new_status=None,history_origin='source_record',_key=key)
    add('BATCH_CREATED','produce_batch',batch.id,batch.created_at,batch.initial_quantity_kg,{'batch_code':batch.batch_code,'crop_name':batch.crop_name})
    allocations=[]
    for record in db.scalars(select(Transaction).where(Transaction.produce_batch_id==batch.id)).all():
        add('PRIMARY_SALE_ACCEPTED','transaction',record.id,record.created_at,record.quantity_kg,{'buyer_id':record.buyer_id,'buyer_requirement_id':record.buyer_requirement_id,'price_per_kg':record.price_per_kg})
        allocations.append((utc(record.created_at),'transaction',record.id,record.quantity_kg))
    for record in db.scalars(select(MatchingAttempt).where(MatchingAttempt.produce_batch_id==batch.id)).all():
        add('PRIMARY_MATCH_ATTEMPTED','matching_attempt',record.id,record.attempted_at,record.remaining_quantity_at_attempt,{'outcome':record.outcome,'compatible_buyers_found':record.compatible_buyers_found})
    for record in db.scalars(select(BuyerRejection).where(BuyerRejection.produce_batch_id==batch.id)).all():
        add('BUYER_REJECTION_RECORDED','buyer_rejection',record.id,record.created_at,record.rejected_quantity_kg,{'reason':record.reason,'buyer_requirement_id':record.buyer_requirement_id,'notes':record.notes})
    for record in db.scalars(select(RoutingCase).where(RoutingCase.produce_batch_id==batch.id)).all():
        add('ROUTING_CASE_CREATED','routing_case',record.id,record.created_at,record.quantity_kg,{'trigger_reason':record.trigger_reason,'trigger_details':{key:value for key,value in record.trigger_details.items() if key not in {'processing_suitability','processing_suitability_by_requirement'}}})
        if 'rerouting_candidate' in record.trigger_details:
            add('RISK_REVIEWED','routing_case',record.id,record.created_at,metadata={key:value for key,value in record.trigger_details.items() if key not in {'processing_suitability','processing_suitability_by_requirement'}})
        for assessment in list(record.trigger_details.get('processing_suitability',{}).values())+list(record.trigger_details.get('processing_suitability_by_requirement',{}).values()):
            if isinstance(assessment,dict) and assessment.get('assessed_at') and assessment.get('intended_utilization'):
                try:
                    timestamp=datetime.fromisoformat(assessment['assessed_at'])
                except (ValueError,TypeError):
                    continue  # Never invent an assessment timestamp.
                add('PROCESSOR_SUITABILITY_RECORDED','routing_case',record.id,timestamp,metadata=assessment,suffix=suitability_suffix(assessment))
    for record in db.scalars(select(AlternativeAllocation).where(AlternativeAllocation.produce_batch_id==batch.id)).all():
        add('ALTERNATIVE_ALLOCATION_ACCEPTED','alternative_allocation',record.id,record.created_at,record.quantity_kg,{'processor_id':record.processor_id,'processor_requirement_id':record.processor_requirement_id,'routing_case_id':record.routing_case_id,'price_per_kg':record.price_per_kg,'intended_utilization':record.intended_utilization,'status':record.status})
        allocations.append((utc(record.created_at),'alternative_allocation',record.id,record.quantity_kg))
    # Only infer the allocation milestone when stored allocations account for the
    # entire initial quantity and the current stored batch has no remaining stock.
    if not any(record.event_type=='BATCH_FULLY_ALLOCATED' for record in recorded) and allocations and batch.remaining_quantity_kg==0 and sum(row[3] for row in allocations)==batch.initial_quantity_kg:
        last=max(allocations,key=lambda row:(row[0],row[1],row[2]))
        add('BATCH_FULLY_ALLOCATED',last[1],last[2],last[0],batch.initial_quantity_kg,{'evidence':'All stored accepted allocation quantities sum to the initial quantity; no utilization is inferred.'})
    # Persisted events supersede their legacy projections, retaining frozen snapshots.
    for record in recorded:
        events[record.event_key]=dict(event_id=record.id,event_type=record.event_type,description=record.event_description,quantity_kg=record.quantity_kg,timestamp=utc(record.created_at),related_entity={'type':record.related_entity_type,'id':record.related_entity_id},metadata=record.event_metadata,previous_status=record.previous_status,new_status=record.new_status,history_origin='recorded_event',_key=record.event_key)
    ordered=sorted(events.values(),key=lambda item:(item['timestamp'],item['_key']))
    for item in ordered:
        item.pop('_key')
    return dict(batch_id=batch.id,batch_code=batch.batch_code,crop_name=batch.crop_name,initial_quantity_kg=batch.initial_quantity_kg,sold_quantity_kg=batch.sold_quantity_kg,remaining_quantity_kg=batch.remaining_quantity_kg,rerouted_quantity_kg=batch.rerouted_quantity_kg,events=ordered)
