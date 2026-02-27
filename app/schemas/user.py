from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List
from uuid import UUID
from datetime import datetime
import re

# Nigerian phone number validation
def validate_nigerian_phone(phone: str) -> str:
    phone = re.sub(r'[\s\-]', '', phone)
    
    if not re.match(r'^(0|\+234|234)[789]\d{9}$', phone):
        raise ValueError('Invalid Nigerian phone number')
    
    if phone.startswith('0'):
        phone = '+234' + phone[1:]
    elif phone.startswith('234'):
        phone = '+' + phone
    
    return phone

class UserBase(BaseModel):
    email: EmailStr
    phone_number: str
    full_name: str
    city: str
    state: str
    lga: Optional[str] = None
    address: Optional[str] = None

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    
    @field_validator('phone_number')
    @classmethod
    def validate_phone(cls, v):
        return validate_nigerian_phone(v)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(UserBase):
    id: UUID
    capabilities: List[str]
    verification_level: str
    is_active: bool
    profile_image: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = {"from_attributes": True}

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse