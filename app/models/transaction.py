from sqlalchemy import Column, String, Float, Text, Enum, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import BaseModel
import builtins
import enum

class TransactionStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    IN_ESCROW = "in_escrow"
    RELEASED = "released"
    REFUNDED = "refunded"
    FAILED = "failed"

class Transaction(BaseModel):
    __tablename__ = "transactions"

    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.id"), nullable=False)
    buyer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    amount = Column(Float, nullable=False)
    platform_fee = Column(Float, nullable=False)
    owner_amount = Column(Float, nullable=False)

    paystack_reference = Column(String(100), unique=True, nullable=False)
    paystack_access_code = Column(String(200), nullable=True)
    authorization_url = Column(String(500), nullable=True)

    status = Column(
        Enum(TransactionStatus),
        default=TransactionStatus.PENDING,
        nullable=False,
    )

    listing_type = Column(String(20), nullable=False)
    release_at = Column(DateTime, nullable=True)
    paid_at = Column(DateTime, nullable=True)
    released_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)

    property = relationship("Property", foreign_keys=[property_id])
    buyer = relationship("User", foreign_keys=[buyer_id])
    owner = relationship("User", foreign_keys=[owner_id])

    @builtins.property
    def property_title(self):
        return self.property.title if self.property else None

    @builtins.property
    def buyer_name(self):
        return self.buyer.full_name if self.buyer else None

    @builtins.property
    def owner_name(self):
        return self.owner.full_name if self.owner else None