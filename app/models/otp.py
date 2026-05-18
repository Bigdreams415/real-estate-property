from sqlalchemy import Column, String, Boolean, DateTime
from app.models.base import BaseModel


class OTPVerification(BaseModel):
    __tablename__ = "otp_verifications"

    phone = Column(String(20), nullable=False, index=True)
    otp_code = Column(String(6), nullable=False)
    is_used = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime, nullable=False)
