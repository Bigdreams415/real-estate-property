from sqlalchemy import Column, String, Integer, Float, Boolean, Text, Enum, ForeignKey, JSON, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import BaseModel
import enum

class PropertyType(str, enum.Enum):
    HOUSE = "house"
    LAND = "land"
    COMMERCIAL = "commercial"
    SHOP = "shop"
    OFFICE = "office"
    WAREHOUSE = "warehouse"
    EVENT_CENTER = "event_center"
    SHORTLET = "shortlet"  

class ListingType(str, enum.Enum):
    RENT = "rent"
    SALE = "sale"
    LEASE = "lease"
    SHORTLET = "shortlet"

class PropertyStatus(str, enum.Enum):
    AVAILABLE = "available"
    RENTED = "rented"
    SOLD = "sold"
    PENDING = "pending"
    UNAVAILABLE = "unavailable"

class PropertyVerificationStatus(str, enum.Enum):
    PENDING_VERIFICATION = "pending_verification"
    VERIFIED = "verified"
    REJECTED = "rejected"

class Property(BaseModel):
    __tablename__ = "properties"
    
    # Basic Info
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    property_type = Column(Enum(PropertyType), nullable=False)
    listing_type = Column(Enum(ListingType), nullable=False)
    status = Column(Enum(PropertyStatus), default=PropertyStatus.AVAILABLE)
    
    # Location
    address = Column(String(255), nullable=False)
    city = Column(String(100), nullable=False)
    state = Column(String(50), nullable=False)
    lga = Column(String(100), nullable=False)   
    landmark = Column(String(100), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    
    # Pricing (in Naira)
    price = Column(Float, nullable=False)
    price_per_unit = Column(String(20), nullable=True)  
    negotiation_allowed = Column(Boolean, default=True)
    service_charge = Column(Float, nullable=True)  
    annual_dues = Column(Float, nullable=True)     
    
    # Property Details
    bedrooms = Column(Integer, nullable=True)
    bathrooms = Column(Integer, nullable=True)
    toilets = Column(Integer, nullable=True)
    square_meters = Column(Float, nullable=True)
    plot_size = Column(String(50), nullable=True)
    
    # Features 
    features = Column(JSON, default=list)  # Flexible features array
    
    # Media
    main_image = Column(String(255), nullable=True)
    
    # Property Verification System
    verification_status = Column(Enum(PropertyVerificationStatus), default=PropertyVerificationStatus.PENDING_VERIFICATION)
    ownership_documents = Column(JSON, default=list)
    verification_notes = Column(Text, nullable=True)
    verified_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    
    # Relationships
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    owner = relationship(
        "User",
        back_populates="properties",
        foreign_keys=[owner_id]
    )
    images = relationship("PropertyImage", back_populates="property", cascade="all, delete-orphan")
    videos = relationship("PropertyVideo", back_populates="property", cascade="all, delete-orphan")
    
    # Views/Engagement
    view_count = Column(Integer, default=0)
    is_featured = Column(Boolean, default=False)

class PropertyImage(BaseModel):
    __tablename__ = "property_images"
    
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.id"), nullable=False)
    image_url = Column(String(255), nullable=False)
    is_main = Column(Boolean, default=False)
    caption = Column(String(100), nullable=True)
    display_order = Column(Integer, default=0)
    
    property = relationship("Property", back_populates="images")

class PropertyVideo(BaseModel):
    __tablename__ = "property_videos"
    
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.id"), nullable=False)
    video_url = Column(String(500), nullable=False)
    thumbnail_url = Column(String(255), nullable=True)
    title = Column(String(100), nullable=True)
    duration = Column(Integer, nullable=True)
    display_order = Column(Integer, default=0)
    
    property = relationship("Property", back_populates="videos")