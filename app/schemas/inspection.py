from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime
from app.models.inspection import InspectionStatus


class InspectionRequest(BaseModel):
    property_id: UUID
    requested_date: datetime
    requester_note: Optional[str] = None


class InspectionReschedule(BaseModel):
    confirmed_date: datetime
    owner_note: Optional[str] = None


class InspectionResponse(BaseModel):
    id: UUID
    property_id: UUID
    requester_id: UUID
    owner_id: UUID
    requested_date: datetime
    confirmed_date: Optional[datetime] = None
    status: InspectionStatus
    requester_note: Optional[str] = None
    owner_note: Optional[str] = None
    requester_name: Optional[str] = None
    owner_name: Optional[str] = None
    property_title: Optional[str] = None
    property_image: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True