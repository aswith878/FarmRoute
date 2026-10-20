from datetime import datetime, timezone
import secrets
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.models.enums import UserRole
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse
from app.schemas.user import UserRead
from app.core.auth import get_current_user, unauthorized
from app.core.security import hash_password, verify_password, create_token, hasher
from app.routes.common import save

router = APIRouter(prefix='/auth', tags=['Authentication'])
# Equalize missing/legacy account password verification work; no usable credential.
_dummy_hash = hash_password(secrets.token_urlsafe(48))


@router.post('/register', response_model=UserRead, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    if payload.role == UserRole.ADMIN:
        raise HTTPException(403, 'ADMIN accounts cannot be publicly registered.')
    email = payload.email.strip().lower()
    if db.scalar(select(User.id).where(func.lower(User.email) == email)) is not None:
        raise HTTPException(409, 'Email already exists.')
    fields = payload.model_dump(exclude={'password'}) | {'email': email}
    return save(db, User(**fields, password_hash=hash_password(payload.password), is_active=True), 'Email already exists.')


@router.post('/login', response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(func.lower(User.email) == payload.email.strip().lower()))
    valid = verify_password(payload.password, user.password_hash if user and user.password_hash else _dummy_hash)
    if not valid or user is None or not user.is_active or not user.password_hash:
        raise unauthorized()
    token = create_token(user.id)
    if hasher.check_needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    return token


@router.get('/me', response_model=UserRead)
def me(user=Depends(get_current_user)):
    return user
