from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


class FieldError(BaseModel):
    field: str
    message: str


class ErrorDetails(BaseModel):
    code: str
    message: str
    field_errors: list[FieldError] = Field(default_factory=list)
    request_id: str | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorDetails


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str, headers: dict | None = None):
        self.status, self.code, self.message = status, code, message
        self.headers = headers


def error_response(request: Request, status: int, code: str, message: str, fields=None, headers=None):
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": code,
                "message": message,
                "field_errors": fields or [],
                "request_id": getattr(request.state, "request_id", None),
            }
        },
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "X-Request-ID": getattr(request.state, "request_id", ""),
            **(headers or {}),
        },
    )
