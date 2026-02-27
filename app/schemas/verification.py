from pydantic import BaseModel, Field, field_validator
import re

class PhoneVerificationRequest(BaseModel):
    phone_number: str
    
    @field_validator('phone_number')
    @classmethod
    def validate_phone(cls, v):
        # Remove spaces and dashes
        phone = re.sub(r'[\s\-]', '', v)
        
        # Validate Nigerian phone number
        if not re.match(r'^(0|\+234|234)[789]\d{9}$', phone):
            raise ValueError('Invalid Nigerian phone number')
        
        # Convert to +234 format
        if phone.startswith('0'):
            phone = '+234' + phone[1:]
        elif phone.startswith('234'):
            phone = '+' + phone
        
        return phone

class VerifyCodeRequest(BaseModel):
    phone_number: str
    code: str = Field(..., min_length=6, max_length=6)
    
    @field_validator('phone_number')
    @classmethod
    def validate_phone(cls, v):
        phone = re.sub(r'[\s\-]', '', v)
        if not re.match(r'^(0|\+234|234)[789]\d{9}$', phone):
            raise ValueError('Invalid Nigerian phone number')
        if phone.startswith('0'):
            phone = '+234' + phone[1:]
        elif phone.startswith('234'):
            phone = '+' + phone
        return phone

class VerificationResponse(BaseModel):
    message: str
    verification_level: str
    capabilities: list[str]