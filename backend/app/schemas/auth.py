from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.schemas.user import UserCreate


class RegisterRequest(UserCreate):
    password: str = Field(min_length=12, max_length=128)

    @field_validator('password', mode='before')
    @classmethod
    def preserve_password(cls, value):
        # Passwords are opaque; do not silently trim whitespace.
        if isinstance(value, str) and (len(value) < 12 or len(value) > 128):
            raise ValueError('Password must contain 12 to 128 characters.')
        return value

    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    expires_at: datetime
