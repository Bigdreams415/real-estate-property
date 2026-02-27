import random
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.user import User
from app.schemas.verification import PhoneVerificationRequest, VerifyCodeRequest, VerificationResponse
from app.api.deps import get_current_active_user

router = APIRouter(prefix="/verification", tags=["Verification"])

@router.post("/phone/send-code", response_model=dict)
async def send_verification_code(
    request: PhoneVerificationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Send SMS verification code (prints to console for now)
    In production, this will integrate with SMS providers
    """
    # Verify the phone number belongs to the current user
    if current_user.phone_number != request.phone_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number does not match your registered number"
        )
    
    # Check if already verified
    if current_user.verification_level != "unverified":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Phone already verified. Current level: {current_user.verification_level}"
        )
    
    # Generate 6-digit code
    code = str(random.randint(100000, 999999))
    
    # Save to database with 10 minute expiry
    current_user.phone_verification_code = code
    current_user.phone_verification_expiry = datetime.utcnow() + timedelta(minutes=10)
    db.commit()
    
    # FOR DEVELOPMENT: Print to console
    print("\n" + "="*50)
    print(f"🔐 VERIFICATION CODE for {current_user.phone_number}")
    print(f"📱 Code: {code}")
    print(f"⏰ Expires in: 10 minutes")
    print("="*50 + "\n")
    
    # In production, you'd call your SMS provider here:
    # send_sms(current_user.phone_number, f"Your verification code: {code}")
    
    return {
        "message": "Verification code sent",
        "expires_in": 10,
        "note": "Check your console for the code (development mode)"
    }

@router.post("/phone/verify", response_model=VerificationResponse)
async def verify_code(
    request: VerifyCodeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Verify the phone number with the received code
    On success: upgrades verification level and adds new capabilities
    """
    # Verify phone number matches
    if current_user.phone_number != request.phone_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number does not match your registered number"
        )
    
    # Check if already verified
    if current_user.verification_level != "unverified":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Already verified. Current level: {current_user.verification_level}"
        )
    
    # Check if code exists
    if not current_user.phone_verification_code or not current_user.phone_verification_expiry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No verification code sent. Please request a new code."
        )
    
    # Check if code expired
    if datetime.utcnow() > current_user.phone_verification_expiry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Code expired. Please request a new code."
        )
    
    # Verify code
    if current_user.phone_verification_code != request.code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code"
        )
    
    # SUCCESS: Upgrade verification level
    current_user.verification_level = "phone_verified"
    
    # Add new capabilities for phone-verified users
    new_capabilities = current_user.capabilities.copy()
    if "contact_landlord" not in new_capabilities:
        new_capabilities.append("contact_landlord")
    if "receive_inquiries" not in new_capabilities:
        new_capabilities.append("receive_inquiries")
    
    current_user.capabilities = new_capabilities
    
    # Clear verification code
    current_user.phone_verification_code = None
    current_user.phone_verification_expiry = None
    
    db.commit()
    db.refresh(current_user)
    
    return VerificationResponse(
        message="Phone verified successfully",
        verification_level=current_user.verification_level,
        capabilities=current_user.capabilities
    )

@router.post("/phone/resend-code", response_model=dict)
async def resend_verification_code(
    request: PhoneVerificationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Resend verification code (with rate limiting)"""
    
    if current_user.phone_number != request.phone_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number does not match your registered number"
        )
    
    if current_user.verification_level != "unverified":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Already verified. Current level: {current_user.verification_level}"
        )
    
    # Check if previous code was sent recently (rate limiting)
    if current_user.phone_verification_expiry:
        time_since_sent = (datetime.utcnow() - (current_user.phone_verification_expiry - timedelta(minutes=10))).total_seconds()
        if time_since_sent < 60:  # 1 minute cooldown
            remaining = 60 - int(time_since_sent)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Please wait {remaining} seconds before requesting another code"
            )
    
    # Generate new code
    code = str(random.randint(100000, 999999))
    
    current_user.phone_verification_code = code
    current_user.phone_verification_expiry = datetime.utcnow() + timedelta(minutes=10)
    db.commit()
    
    print("\n" + "="*50)
    print(f"🔄 NEW VERIFICATION CODE for {current_user.phone_number}")
    print(f"📱 Code: {code}")
    print(f"⏰ Expires in: 10 minutes")
    print("="*50 + "\n")
    
    return {
        "message": "New verification code sent",
        "expires_in": 10
    }

@router.get("/status", response_model=dict)
async def get_verification_status(
    current_user: User = Depends(get_current_active_user)
):
    """Get current user's verification status"""
    return {
        "verification_level": current_user.verification_level,
        "capabilities": current_user.capabilities,
        "is_phone_verified": current_user.verification_level != "unverified",
        "can_contact_landlords": "contact_landlord" in current_user.capabilities,
        "can_list_properties": "create_listing" in current_user.capabilities and 
                               current_user.verification_level in ["identity_verified", "landlord_verified"]
    }
