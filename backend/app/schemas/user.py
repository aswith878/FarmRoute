from pydantic import Field

from app.models.enums import UserRole
from app.schemas.common import ReadFields, SchemaBase, UpdateBase


class UserCreate(SchemaBase):
    name: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=3, max_length=320, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    phone: str | None = Field(default=None, max_length=50)
    role: UserRole


class UserRead(UserCreate, ReadFields):
    is_active: bool


class UserUpdate(UpdateBase):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    is_active: bool | None = None
