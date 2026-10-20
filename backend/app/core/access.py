"""Fail-closed HTTP policy plus SQL collection scoping.

Authorization reads use the identity session. Acceptance services recheck owners
after acquiring their business locks. No inventory calculations live here.
"""
from types import SimpleNamespace
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from app.core.auth import get_current_user, get_identity_db, enforce_owner
from app.models import User, ProduceBatch, BuyerRequirement, ProcessorRequirement, Transaction, RoutingCase, AlternativeAllocation
from app.models.enums import UserRole, RequirementStatus, ProduceStatus
from app.models.routing_case import RoutingCaseStatus
from app.services.matching_service import find_primary_matches, score_requirement
from app.services.processor_matching_service import available_case_quantity


def forbidden():
    raise HTTPException(403, 'You are not authorized to access this record or operation.')


def record(db, model, key):
    row = db.get(model, key)
    if row is None:
        raise HTTPException(404, 'Record not found.')
    return row


def primary_opportunity(db, actor, batch):
    return any(match['buyer_id'] == actor.id for match in find_primary_matches(db, batch)['matches'])


def processor_opportunity(db, actor, case):
    batch = record(db, ProduceBatch, case.produce_batch_id)
    if case.status not in {RoutingCaseStatus.AWAITING_ALTERNATIVE_MATCH, RoutingCaseStatus.MATCHED} or batch.remaining_quantity_kg <= 0 or batch.status in {ProduceStatus.COMPLETED, ProduceStatus.CANCELLED}:
        return False
    # Allow pre-assessment discovery only for own open requirements. Full
    # compatibility is still required by matching and allocation services.
    requirements = db.scalars(select(ProcessorRequirement).where(ProcessorRequirement.processor_id == actor.id,
        ProcessorRequirement.status.in_([RequirementStatus.OPEN, RequirementStatus.PARTIALLY_FILLED]),
        ProcessorRequirement.remaining_requirement_kg > 0)).all()
    grades = {'A': 3, 'B': 2, 'C': 1}
    available = available_case_quantity(db, case, batch)
    if available <= 0:
        return False
    for req in requirements:
        if req.crop_name.casefold() != batch.crop_name.casefold() or (batch.visible_condition or '').strip().upper() not in req.acceptable_produce_conditions or grades.get((batch.quality_grade or '').upper(), 0) < grades.get(req.minimum_acceptable_quality, 99):
            continue
        view = SimpleNamespace(**{name:getattr(req,name) for name in ('id','crop_name','remaining_requirement_kg','minimum_price_per_kg','maximum_price_per_kg','latitude','longitude','maximum_distance_km','pickup_date')},minimum_quality=req.minimum_acceptable_quality)
        if score_requirement(batch, view, actor) is not None:
            return True
    return False


async def authorize_request(request: Request, actor=Depends(get_current_user), db=Depends(get_identity_db)):
    if actor.role == UserRole.ADMIN:
        return
    parts = request.url.path.strip('/').split('/')
    root, method = parts[0], request.method
    try:
        params = {key: int(value) for key, value in request.path_params.items()}
    except (ValueError, TypeError):
        raise HTTPException(422, 'Invalid record identifier.') from None
    role = actor.role
    body = {}
    content_type = request.headers.get('content-type', '').split(';', 1)[0].strip().lower()
    if method in {'POST', 'PUT'} and content_type == 'application/json':
        try:
            body = await request.json()
        except ValueError:
            pass  # FastAPI reports malformed input without echoing it.
        if not isinstance(body, dict):
            body = {}
    if root == 'users':
        if method != 'GET' or len(parts) != 2 or params.get('user_id') != actor.id:
            forbidden()
        return
    if root in {'buyer-requirements', 'processor-requirements'}:
        target_role = UserRole.BUYER if root == 'buyer-requirements' else UserRole.PROCESSOR
        owner_field = 'buyer_id' if target_role == UserRole.BUYER else 'processor_id'
        model = BuyerRequirement if target_role == UserRole.BUYER else ProcessorRequirement
        if role != target_role:
            forbidden()
        if method == 'POST' and len(parts) == 1:
            if owner_field in body:
                enforce_owner(actor, body[owner_field], target_role)
        elif len(parts) > 1:
            enforce_owner(actor, getattr(record(db, model, params['requirement_id']), owner_field), target_role)
        return
    if root == 'produce' or root == 'matches':
        if method == 'POST' and len(parts) == 1:
            if role != UserRole.FARMER:
                forbidden()
            if 'farmer_id' in body:
                enforce_owner(actor, body['farmer_id'], UserRole.FARMER)
            return
        if 'batch_id' not in params:
            if method != 'GET' or role not in {UserRole.FARMER, UserRole.BUYER}:
                forbidden()
            return
        batch = record(db, ProduceBatch, params['batch_id'])
        if role == UserRole.FARMER:
            enforce_owner(actor, batch.farmer_id, UserRole.FARMER)
            # Buyers record their own rejections; farmers cannot impersonate one.
            if parts[-1] == 'rejections':
                forbidden()
            return
        if role == UserRole.BUYER and parts[-1] == 'rejections' and method == 'POST':
            if 'buyer_requirement_id' in body:
                req = record(db, BuyerRequirement, body['buyer_requirement_id'])
                enforce_owner(actor, req.buyer_id, UserRole.BUYER)
            return
        if role == UserRole.BUYER and root == 'produce' and len(parts) == 2 and method == 'GET' and primary_opportunity(db, actor, batch):
            return
        forbidden()
    if root == 'transactions':
        if method == 'POST':
            if role != UserRole.BUYER:
                forbidden()
            if 'buyer_requirement_id' in body:
                enforce_owner(actor, record(db, BuyerRequirement, body['buyer_requirement_id']).buyer_id, UserRole.BUYER)
        elif method == 'GET' and role in {UserRole.BUYER, UserRole.FARMER}:
            if 'transaction_id' in params:
                row = record(db, Transaction, params['transaction_id'])
                if role == UserRole.BUYER:
                    enforce_owner(actor, row.buyer_id, role)
                else:
                    enforce_owner(actor, record(db, ProduceBatch, row.produce_batch_id).farmer_id, role)
        else:
            forbidden()
        return
    if root == 'routing-cases':
        if 'case_id' not in params:
            if method != 'GET' or role not in {UserRole.FARMER, UserRole.PROCESSOR}:
                forbidden()
            return
        case = record(db, RoutingCase, params['case_id'])
        if role == UserRole.FARMER and method == 'GET':
            enforce_owner(actor, record(db, ProduceBatch, case.produce_batch_id).farmer_id, role)
            return
        if role == UserRole.PROCESSOR:
            if method == 'POST' and parts[-1] == 'accept':
                if 'processor_requirement_id' in body:
                    enforce_owner(actor, record(db, ProcessorRequirement, body['processor_requirement_id']).processor_id, role)
                return  # Service checks compatibility and scoped assessment under lock.
            if processor_opportunity(db, actor, case):
                if method == 'POST' and parts[-1] == 'suitability':
                    key = body.get('processor_requirement_id')
                    if key is None:
                        raise HTTPException(422, 'processor_requirement_id is required for processor assessments.')
                    enforce_owner(actor, record(db, ProcessorRequirement, key).processor_id, role)
                return
        forbidden()
    if root == 'alternative-allocations' and method == 'GET' and role in {UserRole.PROCESSOR, UserRole.FARMER}:
        if 'allocation_id' in params:
            row = record(db, AlternativeAllocation, params['allocation_id'])
            if role == UserRole.PROCESSOR:
                enforce_owner(actor, row.processor_id, role)
            else:
                enforce_owner(actor, record(db, ProduceBatch, row.produce_batch_id).farmer_id, role)
        return
    forbidden()


def scope_query(db, query, model):
    actor = db.info.get('actor')
    if actor is None or actor.role == UserRole.ADMIN:
        return query
    if model == ProduceBatch:
        if actor.role == UserRole.FARMER:
            return query.where(ProduceBatch.farmer_id == actor.id)
        candidates = db.scalars(select(ProduceBatch)).all()
        ids = [row.id for row in candidates if primary_opportunity(db, actor, row)]
        return query.where(ProduceBatch.id.in_(ids))
    if model == BuyerRequirement:
        return query.where(model.buyer_id == actor.id)
    if model == ProcessorRequirement:
        return query.where(model.processor_id == actor.id)
    if model == RoutingCase:
        if actor.role == UserRole.FARMER:
            return query.where(model.produce_batch_id.in_(select(ProduceBatch.id).where(ProduceBatch.farmer_id == actor.id)))
        ids = [row.id for row in db.scalars(select(model)).all() if processor_opportunity(db, actor, row)]
        return query.where(model.id.in_(ids))
    if model in {Transaction, AlternativeAllocation}:
        if actor.role == UserRole.FARMER:
            return query.where(model.produce_batch_id.in_(select(ProduceBatch.id).where(ProduceBatch.farmer_id == actor.id)))
        field = model.buyer_id if model == Transaction else model.processor_id
        return query.where(field == actor.id)
    forbidden()


def safe_case(db, case):
    """Processors can read opportunity details, but only their own assessments."""
    from app.schemas.routing_case import RoutingCaseRead
    actor = db.info.get('actor')
    result = RoutingCaseRead.model_validate(case)
    if actor is not None and actor.role == UserRole.PROCESSOR:
        details = dict(result.trigger_details)
        owned = set(str(key) for key in db.scalars(select(ProcessorRequirement.id).where(ProcessorRequirement.processor_id == actor.id)))
        details['processing_suitability_by_requirement'] = {
            key:value for key,value in details.get('processing_suitability_by_requirement',{}).items() if key in owned}
        result.trigger_details = details
    return result
