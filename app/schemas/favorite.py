from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime


class FavoriteResponse(BaseModel):
    id: UUID
    user_id: UUID
    property_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class FavoriteWithProperty(FavoriteResponse):
    property_title: Optional[str] = None
    property_image: Optional[str] = None
    property_price: Optional[float] = None
    property_city: Optional[str] = None
    property_state: Optional[str] = None
    property_type: Optional[str] = None
    listing_type: Optional[str] = None
    view_count: Optional[int] = None
    status: Optional[str] = None


class FavoriteListResponse(BaseModel):
    favorites: list[FavoriteWithProperty]
    total: int


class FavoriteActionResponse(BaseModel):
    message: str
    is_favorited: bool
