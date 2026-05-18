from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import BaseModel


class DeviceToken(BaseModel):
    __tablename__ = "device_tokens"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token = Column(String, nullable=False, unique=True)
    platform = Column(String(10), nullable=False)  # "android" or "ios"
