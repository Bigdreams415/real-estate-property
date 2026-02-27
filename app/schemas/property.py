from pydantic import BaseModel, field_validator
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from app.models.property import PropertyType, ListingType, PropertyStatus, PropertyVerificationStatus


# ─── Image Schemas ────────────────────────────────────────────────────────────

class PropertyImageBase(BaseModel):
    image_url: str          # stored path / CDN URL after upload
    is_main: bool = False
    caption: Optional[str] = None
    display_order: int = 0


class PropertyImageCreate(PropertyImageBase):
    pass


class PropertyImageResponse(PropertyImageBase):
    id: UUID
    property_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Video Schemas ────────────────────────────────────────────────────────────
# Videos stay as external URLs (YouTube / Vimeo) — no file upload

class PropertyVideoBase(BaseModel):
    video_url: str
    thumbnail_url: Optional[str] = None
    title: Optional[str] = None
    duration: Optional[int] = None
    display_order: int = 0


class PropertyVideoCreate(PropertyVideoBase):
    pass


class PropertyVideoResponse(PropertyVideoBase):
    id: UUID
    property_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Ownership Document Schema ────────────────────────────────────────────────
# Each document is now a rich dict, not just a string.
# The dict keys depend on the document type (see frontend DocumentVerificationSection).
# Minimum required key: "document_type"
# Example:
# {
#   "document_type": "Certificate of Occupancy (C of O)",
#   "co_number": "LAG/C-O/2023/00123",
#   "plot_number": "Plot 25",
#   "state_of_issue": "Lagos State",
#   "date_of_issue": "15/03/2021",
#   "issuing_ministry": "Ministry of Lands, Lagos"
# }

class OwnershipDocument(BaseModel):
    document_type: str
    # All other keys are dynamic — accepted as extra fields
    model_config = {"extra": "allow"}

    @field_validator("document_type")
    @classmethod
    def document_type_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("document_type must not be empty")
        return v.strip()


# ─── Property Base ────────────────────────────────────────────────────────────

class PropertyBase(BaseModel):
    title: str
    description: str
    property_type: PropertyType
    listing_type: ListingType
    address: str
    city: str
    state: str
    lga: str
    landmark: Optional[str] = None
    price: float
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    toilets: Optional[int] = None
    square_meters: Optional[float] = None
    plot_size: Optional[str] = None
    features: Optional[List[str]] = []


# ─── Create Schema (used internally after parsing multipart form) ─────────────

class PropertyCreate(PropertyBase):
    # Parsed from the JSON string sent in the multipart 'verification_document' field
    ownership_documents: List[OwnershipDocument] = []
    images: List[PropertyImageCreate] = []
    videos: List[PropertyVideoCreate] = []


# ─── Response Schema ──────────────────────────────────────────────────────────

class PropertyResponse(PropertyBase):
    id: UUID
    status: PropertyStatus
    verification_status: PropertyVerificationStatus
    # Returns full document dicts so admin panel / app can display all fields
    ownership_documents: List[Dict[str, Any]] = []
    verification_notes: Optional[str] = None
    verified_by: Optional[UUID] = None
    verified_at: Optional[datetime] = None
    owner_id: UUID
    view_count: int
    is_featured: bool
    main_image: Optional[str] = None
    images: List[PropertyImageResponse] = []
    videos: List[PropertyVideoResponse] = []
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ─── Admin Verification Action ────────────────────────────────────────────────

class PropertyVerificationAction(BaseModel):
    action: str   # "approve" or "reject"
    notes: Optional[str] = None