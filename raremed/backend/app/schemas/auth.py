import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

RoleName = Literal["user", "clinician", "admin"]


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=10, max_length=128)
    display_name: str | None = Field(default=None, max_length=80)

    @field_validator("email")
    @classmethod
    def email_must_look_valid(cls, value: str) -> str:
        cleaned = value.strip()
        if "@" not in cleaned or "." not in cleaned.split("@")[-1]:
            raise ValueError("Email is not valid.")
        return cleaned

    @field_validator("display_name")
    @classmethod
    def display_name_is_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class UserRead(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    role: RoleName
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionRead(BaseModel):
    user: UserRead


class UserRoleUpdate(BaseModel):
    role: RoleName | None = None
    is_active: bool | None = None
