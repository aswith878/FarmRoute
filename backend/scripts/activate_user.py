"""Local, interactive credential activation; no password command-line argument."""
import argparse
import getpass
import sys
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from app.database import SessionLocal
from app.models import User
from app.core.security import hash_password


def main():
    parser = argparse.ArgumentParser(description='Activate an existing account using a securely prompted password.')
    parser.add_argument('user_id', type=int)
    args = parser.parse_args()
    if not sys.stdin.isatty():
        raise SystemExit('Run activation in an interactive terminal; password echo fallback is disabled.')
    password = getpass.getpass('New password (12–128 characters): ')
    confirm = getpass.getpass('Confirm password: ')
    if password != confirm or not 12 <= len(password) <= 128:
        raise SystemExit('Passwords must match and contain 12–128 characters.')
    try:
        with SessionLocal.begin() as db:
            user = db.scalar(select(User).where(User.id == args.user_id).with_for_update())
            if user is None or not user.is_active:
                raise SystemExit('Account not found or inactive. No credential changed.')
            user.password_hash = hash_password(password)
    except SQLAlchemyError:
        raise SystemExit('Credential activation failed. Database details are suppressed.') from None
    print('Credential activated. No password or hash is displayed.')


if __name__ == '__main__':
    main()
