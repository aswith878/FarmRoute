"""Password and access-token primitives. Secrets never enter API responses."""
import os
from datetime import datetime, timedelta, timezone
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError

ISSUER = 'agriroute-api'
AUDIENCE = 'agriroute'
hasher = PasswordHasher()


def settings():
    secret = os.getenv('JWT_SECRET', '')
    if len(secret.encode()) < 32 or secret.startswith('replace-with-'):
        raise RuntimeError('Set JWT_SECRET to a random secret of at least 32 bytes in backend/.env.')
    try:
        minutes = int(os.getenv('JWT_ACCESS_TOKEN_EXPIRE_MINUTES', '30'))
        if not 1 <= minutes <= 1440:
            raise ValueError
    except ValueError:
        raise RuntimeError('JWT_ACCESS_TOKEN_EXPIRE_MINUTES must be between 1 and 1440.') from None
    return secret, minutes


def hash_password(password):
    return hasher.hash(password)


def verify_password(password, encoded):
    try:
        return hasher.verify(encoded, password)
    except (VerificationError, InvalidHashError, TypeError):
        return False


def create_token(user_id):
    secret, minutes = settings()
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=minutes)
    token = jwt.encode({'sub': str(user_id), 'iat': now, 'exp': expires,
                        'iss': ISSUER, 'aud': AUDIENCE}, secret, algorithm='HS256')
    return {'access_token': token, 'token_type': 'bearer', 'expires_in': minutes * 60,
            'expires_at': expires}


def decode_token(token):
    secret, _ = settings()
    claims = jwt.decode(token, secret, algorithms=['HS256'], audience=AUDIENCE,
                        issuer=ISSUER, options={'require': ['sub', 'exp', 'iat', 'iss', 'aud']})
    subject = claims['sub']
    if not isinstance(subject, str) or not subject.isdecimal() or int(subject) <= 0:
        raise jwt.InvalidTokenError()
    return int(subject)
