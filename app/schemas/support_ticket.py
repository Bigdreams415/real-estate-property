from pydantic import BaseModel, field_validator
from typing import Optional
from uuid import UUID
from datetime import datetime

_VALID_CATEGORIES = {"bug", "payment", "report_listing", "account", "other"}
_VALID_STATUSES = {"open", "in_progress", "resolved", "closed"}


class SupportTicketCreate(BaseModel):
    category: str
    subject: str
    message: str

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        if v not in _VALID_CATEGORIES:
            raise ValueError(f"category must be one of {sorted(_VALID_CATEGORIES)}")
        return v

    @field_validator("subject")
    @classmethod
    def validate_subject(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("subject cannot be empty")
        if len(v) > 200:
            raise ValueError("subject too long (max 200 characters)")
        return v

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 10:
            raise ValueError("message too short (min 10 characters)")
        if len(v) > 2000:
            raise ValueError("message too long (max 2000 characters)")
        return v


class SupportTicketResponse(BaseModel):
    id: UUID
    user_id: UUID
    category: str
    subject: str
    message: str
    status: str
    admin_reply: Optional[str]
    replied_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


class SupportTicketListResponse(BaseModel):
    tickets: list[SupportTicketResponse]
    total: int


class SupportTicketAdminUpdate(BaseModel):
    status: Optional[str] = None
    admin_reply: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in _VALID_STATUSES:
            raise ValueError(f"status must be one of {sorted(_VALID_STATUSES)}")
        return v

    @field_validator("admin_reply")
    @classmethod
    def validate_admin_reply(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if len(v) > 2000:
                raise ValueError("admin_reply too long (max 2000 characters)")
        return v


class AdminTicketResponse(SupportTicketResponse):
    user_email: str
    user_full_name: str


class AdminTicketListResponse(BaseModel):
    tickets: list[AdminTicketResponse]
    total: int
