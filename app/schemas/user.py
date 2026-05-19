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
    full_name: str
    phone_number: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    lga: Optional[str] = None
    address: Optional[str] = None

class UserCreate(UserBase):
    # Local signup — phone, city, state are required
    phone_number: str
    city: str
    state: str
    password: str = Field(..., min_length=8)

    @field_validator('phone_number')
    @classmethod
    def validate_phone(cls, v):
        return validate_nigerian_phone(v)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class GoogleAuthRequest(BaseModel):
    id_token: str

class CompleteProfileRequest(BaseModel):
    phone_number: str
    city: str
    state: str
    lga: Optional[str] = None
    address: Optional[str] = None

    @field_validator('phone_number')
    @classmethod
    def validate_phone(cls, v):
        return validate_nigerian_phone(v)

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)

class ChangePhoneRequest(BaseModel):
    phone_number: str

    @field_validator('phone_number')
    @classmethod
    def validate_phone(cls, v):
        return validate_nigerian_phone(v)

class LoginAlertsRequest(BaseModel):
    enabled: bool

class UserResponse(UserBase):
    id: UUID
    capabilities: List[str]
    verification_level: str
    is_active: bool
    auth_provider: str
    is_profile_complete: bool
    login_alerts_enabled: bool = True
    profile_image: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
