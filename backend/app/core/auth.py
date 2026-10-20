"""Identity uses a separate read session from business transactions."""
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import SessionLocal, get_db
from app.models import User
from app.models.enums import UserRole
from app.core.security import decode_token

bearer = HTTPBearer(auto_error=False, description='Paste the access_token returned by POST /auth/login.')


def get_identity_db():
    with SessionLocal() as db:
        yield db


def unauthorized():
    return HTTPException(401, 'Invalid or missing authentication credentials.', headers={'WWW-Authenticate': 'Bearer'})


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
                     db: Session = Depends(get_identity_db)):
    if credentials is None or credentials.scheme.lower() != 'bearer':
        raise unauthorized()
    try:
        user_id = decode_token(credentials.credentials)
    except jwt.InvalidTokenError:
        raise unauthorized() from None
    user = db.get(User, user_id)
    if user is None or not user.is_active or not user.password_hash:
        raise unauthorized()
    return user


def require_roles(*roles):
    def check(user=Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(403, 'This role is not authorized for this operation.')
        return user
    return check


def enforce_owner(actor, owner_id, role):
    # Internal trusted scripts can use services without an HTTP actor.
    if actor is not None and actor.role != UserRole.ADMIN:
        if actor.role != role or actor.id != owner_id:
            raise HTTPException(403, 'You do not own this record.')


def get_authorized_db(db: Session = Depends(get_db), actor=Depends(get_current_user)):
    db.info['actor'] = actor
    return db
