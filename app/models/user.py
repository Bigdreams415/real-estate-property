from sqlalchemy import Column, String, Boolean, Text, JSON, DateTime
from sqlalchemy.orm import relationship
from app.models.base import BaseModel

class User(BaseModel):
    __tablename__ = "users"
    
    email = Column(String(100), unique=True, index=True, nullable=False)
    phone_number = Column(String(20), unique=True, index=True, nullable=False)  
    full_name = Column(String(100), nullable=False)
    password_hash = Column(String(255), nullable=False)
    
    capabilities = Column(JSON, default=["browse_properties", "save_favorites"])
    verification_level = Column(String(20), default="unverified")
    
    is_active = Column(Boolean, default=True)
    
    profile_image = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    city = Column(String(100), nullable=False)  
    state = Column(String(50), nullable=False)   
    lga = Column(String(100), nullable=True)   
    
    phone_verification_code = Column(String(6), nullable=True)
    phone_verification_expiry = Column(DateTime, nullable=True)
    
    means_of_identification = Column(String(255), nullable=True)
    identification_number = Column(String(50), nullable=True)
    
    from app.models.property import Property
    properties = relationship(
        "Property",
        back_populates="owner",
        foreign_keys="Property.owner_id"
    )