from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from app.models.transaction import TransactionStatus


class InitiatePaymentRequest(BaseModel):
    property_id: UUID


class TransactionResponse(BaseModel):
    id: UUID
    property_id: UUID
    buyer_id: UUID
    owner_id: UUID
    amount: float
    platform_fee: float
    owner_amount: float
    paystack_reference: str
    authorization_url: Optional[str] = None
    status: TransactionStatus
    listing_type: str
    release_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    released_at: Optional[datetime] = None
    notes: Optional[str] = None
    property_title: Optional[str] = None
    property_image: Optional[str] = None
    property_city: Optional[str] = None
    property_state: Optional[str] = None
    escrow_seconds_remaining: Optional[int] = None
    buyer_name: Optional[str] = None
    owner_name: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TransactionListResponse(BaseModel):
    items: List[TransactionResponse]
    total: int