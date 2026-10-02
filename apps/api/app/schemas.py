"""Public request and response contracts for M1."""

import re

from pydantic import BaseModel, Field, field_validator


PHONE_PATTERN = re.compile(r"^\+?[0-9]{8,15}$")


class RegisterRequest(BaseModel):
    phone: str = Field(max_length=20)
    verification_code: str = Field(min_length=4, max_length=8)
    password: str = Field(min_length=8, max_length=72)
    display_name: str = Field(min_length=1, max_length=80)

    @field_validator("phone")
    @classmethod
    def valid_phone(cls, value: str) -> str:
        if not PHONE_PATTERN.fullmatch(value):
            raise ValueError("手机号格式不正确")
        return value


class LoginRequest(BaseModel):
    account: str = Field(min_length=1)
    password: str


class UserResponse(BaseModel):
    id: int
    display_name: str
    phone_masked: str | None
    roles: list[str]
    status: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class ErrorResponse(BaseModel):
    code: str
    message: str
    request_id: str
    details: dict | None = None


def public_user(user) -> UserResponse:
    phone = user.phone
    if phone and len(phone) > 7:
        phone = phone[:3] + "****" + phone[-4:]
    return UserResponse(
        id=user.id,
        display_name=user.display_name,
        phone_masked=phone,
        roles=sorted(role.code for role in user.roles),
        status=user.status,
    )

