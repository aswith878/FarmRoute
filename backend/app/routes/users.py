from app.core.auth import get_authorized_db
from app.core.access import authorize_request, scope_query
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.models.enums import UserRole
from app.routes.common import apply_update, get_or_404, save
from app.schemas.user import UserCreate, UserRead, UserUpdate

router = APIRouter(dependencies=[Depends(authorize_request)], prefix="/users", tags=["Users"])


@router.post("", response_model=UserRead, status_code=201)
def create_user(payload: UserCreate, db: Session = Depends(get_authorized_db)):
    if db.scalar(select(User.id).where(User.email == payload.email)) is not None:
        raise HTTPException(status_code=409, detail="Email already exists.")
    return save(db, User(**payload.model_dump(), is_active=True), "Email already exists.")


@router.get("", response_model=list[UserRead])
def list_users(role: UserRole | None = None, is_active: bool | None = None, db: Session = Depends(get_authorized_db)):
    query = select(User).order_by(User.id)
    if role is not None:
        query = query.where(User.role == role)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    return db.scalars(query).all()


@router.get("/{user_id}", response_model=UserRead)
def read_user(user_id: int, db: Session = Depends(get_authorized_db)):
    return get_or_404(db, User, user_id)


@router.put("/{user_id}", response_model=UserRead)
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_authorized_db)):
    user = get_or_404(db, User, user_id)
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("is_active") is False:
        actor = db.info.get("actor")
        if actor is not None and actor.id == user.id:
            raise HTTPException(status_code=409, detail="You cannot deactivate your own account.")
        if user.role == UserRole.ADMIN and user.is_active:
            active_admins = db.scalars(
                select(User)
                .where(User.role == UserRole.ADMIN, User.is_active.is_(True))
                .order_by(User.id)
                .with_for_update()
            ).all()
            if len(active_admins) <= 1:
                raise HTTPException(status_code=409, detail="The last active administrator cannot be deactivated.")
    apply_update(user, payload)
    return save(db, user)
