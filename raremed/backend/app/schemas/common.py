from typing import Literal

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    location: list[str]
    message: str


class ErrorObject(BaseModel):
    code: str
    message: str
    request_id: str
    details: list[ErrorDetail] | None = None


class ErrorResponse(BaseModel):
    error: ErrorObject


class DependencyStatus(BaseModel):
    status: Literal["ok", "unavailable"]
    detail: str | None = None


LocaleCode = Literal["en", "fr", "ar", "ary"]
