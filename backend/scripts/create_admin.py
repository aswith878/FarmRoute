"""Explicit local administrator bootstrap; never called at startup or migration."""
import getpass
import sys
from sqlalchemy.exc import SQLAlchemyError
from pydantic import ValidationError
from app.database import SessionLocal
from app.models import User
from app.schemas.user import UserCreate
from app.core.security import hash_password


def main():
    if not sys.stdin.isatty():
        raise SystemExit('Run administrator bootstrap in an interactive terminal.')
    try:
        profile = UserCreate(name=input('Administrator name: '),email=input('Administrator email: ').strip().lower(),role='ADMIN')
    except ValidationError:
        raise SystemExit('Invalid name or email. No account created.') from None
    password = getpass.getpass('Password (12–128 characters): ')
    confirm = getpass.getpass('Confirm password: ')
    if password != confirm or not 12 <= len(password) <= 128:
        raise SystemExit('Passwords must match and contain 12–128 characters.')
    try:
        with SessionLocal.begin() as db:
            db.add(User(**profile.model_dump(),password_hash=hash_password(password),is_active=True))
    except SQLAlchemyError:
        raise SystemExit('Administrator creation failed; check email uniqueness and database availability. Details suppressed.') from None
    print('Administrator created. No password or hash is displayed.')


if __name__ == '__main__':
    main()
