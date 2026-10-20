from app.core.auth import get_authorized_db
from app.core.access import authorize_request, scope_query
import re
import os
import uuid
from decimal import Decimal
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ProduceBatch
from app.models.enums import ProduceStatus, RiskLevel, UserRole
from app.routes.common import apply_update, get_or_404, require_owner, save
from app.schemas.produce_batch import ProduceBatchCreate, ProduceBatchRead, ProduceBatchUpdate
from app.services.traceability_service import record_event

router = APIRouter(dependencies=[Depends(authorize_request)], prefix="/produce", tags=["Produce"])

MAX_IMAGE_BYTES = 5 * 1024 * 1024
IMAGE_TYPES = {
    "image/png": ("png", lambda data: data.startswith(b"\x89PNG\r\n\x1a\n")),
    "image/jpeg": ("jpg", lambda data: data.startswith(b"\xff\xd8\xff")),
    "image/webp": ("webp", lambda data: len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"),
}
IMAGE_BUCKET = "agriroute-produce-images"


def storage_headers(key: str, content_type: str | None = None):
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    if content_type:
        headers["Content-Type"] = content_type
    return headers


@router.post("/{batch_id}/image", response_model=ProduceBatchRead)
def upload_produce_image(batch_id: int, image: UploadFile = File(...), db: Session = Depends(get_authorized_db)):
    """Store a listing photo in Supabase Storage through the server-only key."""
    batch = get_or_404(db, ProduceBatch, batch_id)
    actor = db.info.get("actor")
    if actor is None or actor.role != UserRole.FARMER or actor.id != batch.farmer_id:
        raise HTTPException(status_code=403, detail="Only the owning farmer can upload this batch image.")
    if batch.image_url:
        raise HTTPException(status_code=409, detail="An image is already saved for this batch.")

    mime = image.content_type or ""
    image_type = IMAGE_TYPES.get(mime)
    if image_type is None:
        raise HTTPException(status_code=415, detail="Use a PNG, JPEG, or WebP image.")
    content = image.file.read(MAX_IMAGE_BYTES + 1)
    if not content or len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image must be smaller than 5 MB.")
    extension, matches_signature = image_type
    if not matches_signature(content):
        raise HTTPException(status_code=415, detail="The selected file does not match its image type.")

    project_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not project_url.startswith("https://") or not service_key or service_key.startswith("replace-with-"):
        raise HTTPException(status_code=503, detail="Image storage is not configured on the API.")

    object_path = f"farmers/{actor.id}/batches/{batch.id}/{uuid.uuid4().hex}.{extension}"
    encoded_path = quote(object_path, safe="/")
    object_url = f"{project_url}/storage/v1/object/{IMAGE_BUCKET}/{encoded_path}"
    public_url = f"{project_url}/storage/v1/object/public/{IMAGE_BUCKET}/{encoded_path}"
    headers = storage_headers(service_key, mime)
    try:
        with httpx.Client(timeout=20) as client:
            response = client.post(object_url, headers=headers, content=content)
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="Image storage could not be reached.") from None
    if not response.is_success:
        raise HTTPException(status_code=502, detail="Image storage rejected the upload.")

    batch.image_url = public_url
    try:
        db.commit()
        db.refresh(batch)
    except SQLAlchemyError:
        db.rollback()
        try:
            with httpx.Client(timeout=10) as client:
                client.delete(object_url, headers=storage_headers(service_key))
        except httpx.RequestError:
            pass
        raise HTTPException(status_code=500, detail="Image metadata could not be saved.") from None
    return batch


def generate_batch_code(db: Session, crop_name: str) -> str:
    crop = (re.sub(r"[^A-Z]", "", crop_name.upper())[:3] or "CRP").ljust(3, "X")
    prefix = f"AGR-{crop}-"
    # PostgreSQL transaction lock serializes generation through commit; no new table.
    db.execute(text("SELECT pg_advisory_xact_lock(1594470001)"))
    codes = db.scalars(select(ProduceBatch.batch_code).where(ProduceBatch.batch_code.startswith(prefix))).all()
    numbers = [int(code[len(prefix):]) for code in codes if code[len(prefix):].isdigit()]
    number = max(numbers, default=0) + 1
    if number > 9999:
        raise HTTPException(status_code=409, detail="Batch code range exhausted for this crop prefix.")
    return f"{prefix}{number:04d}"


@router.post("", response_model=ProduceBatchRead, status_code=201)
def create_produce(payload: ProduceBatchCreate, db: Session = Depends(get_authorized_db)):
    require_owner(db, payload.farmer_id, UserRole.FARMER)
    batch = ProduceBatch(
        **payload.model_dump(), batch_code=generate_batch_code(db, payload.crop_name),
        sold_quantity_kg=Decimal("0"), rerouted_quantity_kg=Decimal("0"),
        remaining_quantity_kg=payload.initial_quantity_kg, status=ProduceStatus.ACTIVE,
    )
    return save(db, batch, before_commit=lambda session,record: record_event(session,record,'BATCH_CREATED','produce_batch',record.id,quantity=record.initial_quantity_kg,timestamp=record.created_at,new_status=record.status,metadata={'batch_code':record.batch_code,'crop_name':record.crop_name}))


@router.get("", response_model=list[ProduceBatchRead])
def list_produce(farmer_id: int | None = None, crop_name: str | None = None, status: ProduceStatus | None = None, risk_level: RiskLevel | None = None, db: Session = Depends(get_authorized_db)):
    query = select(ProduceBatch).order_by(ProduceBatch.id)
    for field, value in ((ProduceBatch.farmer_id, farmer_id), (ProduceBatch.crop_name, crop_name), (ProduceBatch.status, status), (ProduceBatch.risk_level, risk_level)):
        if value is not None:
            query = query.where(field == value)
    return db.scalars(scope_query(db, query, ProduceBatch)).all()


@router.get("/{batch_id}", response_model=ProduceBatchRead)
def read_produce(batch_id: int, db: Session = Depends(get_authorized_db)):
    return get_or_404(db, ProduceBatch, batch_id)


@router.put("/{batch_id}", response_model=ProduceBatchRead)
def update_produce(batch_id: int, payload: ProduceBatchUpdate, db: Session = Depends(get_authorized_db)):
    batch = get_or_404(db, ProduceBatch, batch_id)
    apply_update(batch, payload)
    return save(db, batch)
