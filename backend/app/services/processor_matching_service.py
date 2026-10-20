"""Primary and processor recommendations remain separate; no allocation writes."""
from decimal import Decimal
from types import SimpleNamespace
from sqlalchemy import func, select
from app.models import AlternativeAllocation, ProcessorRequirement, User
from app.models.enums import RequirementStatus, UserRole, ProduceStatus
from app.models.routing_case import RoutingCaseStatus
from app.services.matching_service import score_requirement

WEIGHTS={'crop':10,'quantity':15,'quality':10,'condition':10,'suitability':20,'price':10,'distance':10,'pickup':10,'urgency':5}
ACTIVE_CASE_STATUSES=(RoutingCaseStatus.AWAITING_ALTERNATIVE_MATCH,RoutingCaseStatus.MATCHED)


def available_case_quantity(db,case,batch):
    allocated=db.scalar(select(func.coalesce(func.sum(AlternativeAllocation.quantity_kg),0)).where(AlternativeAllocation.routing_case_id==case.id))
    return max(Decimal('0'),min(batch.remaining_quantity_kg,case.quantity_kg-allocated))


def compatibility(case,batch,requirement,processor,available):
    if available<=0 or processor.role!=UserRole.PROCESSOR or not processor.is_active:
        return None
    if requirement.status not in {RequirementStatus.OPEN,RequirementStatus.PARTIALLY_FILLED} or requirement.remaining_requirement_kg<=0:
        return None
    condition=(batch.visible_condition or '').strip().upper()
    if not condition or condition not in requirement.acceptable_produce_conditions:
        return None
    details=case.trigger_details or {}
    assessment=details.get('processing_suitability_by_requirement',{}).get(str(requirement.id))
    if assessment is None:
        assessment=details.get('processing_suitability',{}).get(requirement.intended_utilization)
    if not isinstance(assessment,dict) or assessment.get('suitable') is not True:
        return None
    risk=getattr(batch.risk_level,'value',batch.risk_level)
    if assessment.get('confirmed_condition')!=condition or assessment.get('crop_name')!=batch.crop_name or assessment.get('quality_grade')!=batch.quality_grade or assessment.get('risk_level')!=risk:
        return None
    # Unknown grades cannot establish processor suitability.
    if (batch.quality_grade or '').upper() not in {'A','B','C'} or requirement.minimum_acceptable_quality not in {'A','B','C'}:
        return None
    batch_view=SimpleNamespace(**{name:getattr(batch,name) for name in ('crop_name','quality_grade','expected_price_per_kg','latitude','longitude','harvest_date','available_until','risk_level')},remaining_quantity_kg=available)
    requirement_view=SimpleNamespace(**{name:getattr(requirement,name) for name in ('id','crop_name','remaining_requirement_kg','minimum_price_per_kg','maximum_price_per_kg','latitude','longitude','maximum_distance_km','pickup_date')},minimum_quality=requirement.minimum_acceptable_quality)
    result=score_requirement(batch_view,requirement_view,processor)
    if result is None:
        return None
    scores=result['score_breakdown'] | {'condition':100,'suitability':100}
    return dict(processor_id=processor.id,processor_name=processor.name,processor_requirement_id=requirement.id,compatible_quantity_kg=result['matchable_quantity_kg'],distance_km=result['distance_km'],match_score=round(sum(scores[key]*weight for key,weight in WEIGHTS.items())/100,2),score_breakdown=scores,suitability_explanation=f"Explicit assessment by {assessment['assessed_by']} for {requirement.intended_utilization}: {assessment['assessment_notes']}. This records an assessment, not proof of delivery or utilization.",intended_utilization=requirement.intended_utilization,warnings=result['warnings'])


def find_processor_matches(db,case,batch):
    available=available_case_quantity(db,case,batch)
    result=dict(routing_case_id=case.id,available_quantity_kg=available,matches=[],warnings=[])
    if case.status not in ACTIVE_CASE_STATUSES or batch.status in {ProduceStatus.CANCELLED,ProduceStatus.COMPLETED} or available<=0:
        result['warnings'].append('Routing case is terminal or has no currently allocatable inventory.')
        return result
    candidates=db.execute(select(ProcessorRequirement,User).join(User,ProcessorRequirement.processor_id==User.id).where(User.role==UserRole.PROCESSOR,User.is_active.is_(True),ProcessorRequirement.status.in_([RequirementStatus.OPEN,RequirementStatus.PARTIALLY_FILLED]),ProcessorRequirement.remaining_requirement_kg>0,func.lower(ProcessorRequirement.crop_name)==batch.crop_name.lower())).all()
    if not (case.trigger_details or {}).get('processing_suitability'):
        result['warnings'].append('Explicit processing suitability assessment is missing; destinations are excluded pending human verification.')
    for requirement,processor in candidates:
        match=compatibility(case,batch,requirement,processor,available)
        if match:
            result['matches'].append(match)
    result['matches'].sort(key=lambda row:(-row['match_score'],row['processor_requirement_id']))
    return result
