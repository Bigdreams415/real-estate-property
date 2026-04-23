from sqlalchemy import Column, String, Text, Enum, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import BaseModel
import enum

class InspectionStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    RESCHEDULED = "rescheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class Inspection(BaseModel):
    __tablename__ = "inspections"

    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.id"), nullable=False)
    requester_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    requested_date = Column(DateTime, nullable=False)
    confirmed_date = Column(DateTime, nullable=True)

    status = Column(
        Enum(InspectionStatus),
        default=InspectionStatus.PENDING,
        nullable=False,
    )

    requester_note = Column(Text, nullable=True)
    owner_note = Column(Text, nullable=True)

    property = relationship("Property", foreign_keys=[property_id])
    requester = relationship("User", foreign_keys=[requester_id])
    owner = relationship("User", foreign_keys=[owner_id])

    @property
    def requester_name(self):
        return self.requester.full_name if self.requester else None

    @property
    def owner_name(self):
        return self.owner.full_name if self.owner else None

    @property
    def property_title(self):
        return self.property.title if self.property else None

    @property
    def property_image(self):
        return self.property.main_image if self.property else None