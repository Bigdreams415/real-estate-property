import hmac
import hashlib
import uuid
import httpx
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List
from uuid import UUID
from app.core.database import get_db
from app.core.config import settings
from app.models.transaction import Transaction, TransactionStatus
from app.models.property import Property
from app.models.user import User
from app.schemas.transaction import InitiatePaymentRequest, TransactionResponse
from app.api.deps import get_current_active_user, require_capability

router = APIRouter(prefix="/payments", tags=["Payments"])

PLATFORM_FEE_PERCENT = 0.08  # 8% platform commission
ESCROW_HOLD_HOURS = 72       # hours before auto-release


def _kobo(amount: float) -> int:
    """Convert Naira to kobo for Paystack."""
    return int(amount * 100)


@router.post("/initiate", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def initiate_payment(
    payload: InitiatePaymentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Initialize a Paystack transaction for a property."""

    prop = db.query(Property).filter(Property.id == payload.property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found.")

    if str(prop.owner_id) == str(current_user.id):
        raise HTTPException(status_code=400, detail="You cannot pay for your own property.")

    # Prevent duplicate pending transaction
    existing = db.query(Transaction).filter(
        Transaction.property_id == payload.property_id,
        Transaction.buyer_id == current_user.id,
        Transaction.status.in_([TransactionStatus.PENDING, TransactionStatus.IN_ESCROW]),
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail="You already have an active transaction for this property.",
        )

    amount = prop.price
    platform_fee = round(amount * PLATFORM_FEE_PERCENT, 2)
    owner_amount = round(amount - platform_fee, 2)
    reference = f"DP-{uuid.uuid4().hex[:16].upper()}"

    # Call Paystack to initialize transaction
    async with httpx.AsyncClient() as client:
        paystack_response = await client.post(
            "https://api.paystack.co/transaction/initialize",
            headers={
                "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "email": current_user.email,
                "amount": _kobo(amount),
                "reference": reference,
                "metadata": {
                    "property_id": str(prop.id),
                    "property_title": prop.title,
                    "buyer_id": str(current_user.id),
                    "owner_id": str(prop.owner_id),
                },
                "callback_url": f"{settings.APP_BASE_URL}/api/v1/payments/callback",
            },
        )

    if paystack_response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail="Failed to initialize payment with Paystack.",
        )

    paystack_data = paystack_response.json()["data"]

    transaction = Transaction(
        property_id=prop.id,
        buyer_id=current_user.id,
        owner_id=prop.owner_id,
        amount=amount,
        platform_fee=platform_fee,
        owner_amount=owner_amount,
        paystack_reference=reference,
        paystack_access_code=paystack_data.get("access_code"),
        authorization_url=paystack_data.get("authorization_url"),
        listing_type=prop.listing_type.value,
        status=TransactionStatus.PENDING,
    )

    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


@router.post("/webhook")
async def paystack_webhook(request: Request, db: Session = Depends(get_db)):
    """Paystack calls this when a payment completes."""

    body = await request.body()
    signature = request.headers.get("x-paystack-signature", "")

    # Verify webhook signature
    expected = hmac.new(
        settings.PAYSTACK_SECRET_KEY.encode(),
        body,
        hashlib.sha512,
    ).hexdigest()

    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=400, detail="Invalid signature.")

    import json
    event = json.loads(body)

    if event.get("event") != "charge.success":
        return {"status": "ignored"}

    reference = event["data"]["reference"]
    transaction = db.query(Transaction).filter(
        Transaction.paystack_reference == reference
    ).first()

    if not transaction:
        return {"status": "transaction not found"}

    if transaction.status != TransactionStatus.PENDING:
        return {"status": "already processed"}

    transaction.status = TransactionStatus.IN_ESCROW
    transaction.paid_at = datetime.utcnow()
    transaction.release_at = datetime.utcnow() + timedelta(hours=ESCROW_HOLD_HOURS)

    db.commit()
    return {"status": "success"}


@router.post("/verify/{reference}", response_model=TransactionResponse)
async def verify_payment(
    reference: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Flutter calls this after returning from Paystack to confirm payment."""

    transaction = db.query(Transaction).filter(
        Transaction.paystack_reference == reference,
        Transaction.buyer_id == current_user.id,
    ).first()

    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found.")

    if transaction.status != TransactionStatus.PENDING:
        return transaction

    # Verify with Paystack directly
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.paystack.co/transaction/verify/{reference}",
            headers={"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"},
        )

    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="Could not verify with Paystack.")

    data = response.json()["data"]

    if data["status"] == "success":
        transaction.status = TransactionStatus.IN_ESCROW
        transaction.paid_at = datetime.utcnow()
        transaction.release_at = datetime.utcnow() + timedelta(hours=ESCROW_HOLD_HOURS)
        db.commit()
        db.refresh(transaction)

    return transaction


@router.get("/mine", response_model=List[TransactionResponse])
async def get_my_transactions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get all transactions where current user is buyer or owner."""
    transactions = db.query(Transaction).filter(
        or_(
            Transaction.buyer_id == current_user.id,
            Transaction.owner_id == current_user.id,
        )
    ).order_by(Transaction.created_at.desc()).all()
    return transactions


@router.post("/{transaction_id}/release", response_model=TransactionResponse)
async def release_funds(
    transaction_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_capability("admin_access")),
):
    """Admin manually releases escrow funds to landlord."""
    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id
    ).first()

    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found.")

    if transaction.status != TransactionStatus.IN_ESCROW:
        raise HTTPException(
            status_code=400,
            detail=f"Transaction is {transaction.status}, not in escrow.",
        )

    transaction.status = TransactionStatus.RELEASED
    transaction.released_at = datetime.utcnow()
    db.commit()
    db.refresh(transaction)
    return transaction