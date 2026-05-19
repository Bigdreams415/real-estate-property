from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.core.database import get_db
from app.models.user import User
from app.services.otp_service import OTPService
from app.services.sms_service import get_sms_client
from app.api.deps import get_current_active_user
from app.utils.auth import create_access_token

router = APIRouter(prefix="/otp", tags=["OTP"])


class OTPSendResponse(BaseModel):
    message: str
    expires_in_minutes: int = 10
    sms_sent: bool = True


class OTPVerifyRequest(BaseModel):
    code: str


class OTPVerifyResponse(BaseModel):
    message: str
    verified: bool
    access_token: str
    verification_level: str


@router.post("/send", response_model=OTPSendResponse)
async def send_otp(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Generate an OTP and send it to the user's registered phone number."""
    if not current_user.phone_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No phone number on file. Please complete your profile first.",
        )

    if current_user.verification_level != "unverified":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone already verified.",
        )

    # First send on screen load — skip rate limit check
    otp = OTPService.create_otp(db, current_user.phone_number, check_rate_limit=False)

    sms_client = get_sms_client()
    message = f"RentalGuide: {otp.otp_code} — use this to complete your login. Expires in 10 mins."

    result = await sms_client.send_sms(to=current_user.phone_number, message=message)
    sms_sent = bool(result)

    return OTPSendResponse(message="OTP sent to your registered phone number.", sms_sent=sms_sent)


@router.post("/resend", response_model=OTPSendResponse)
async def resend_otp(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Resend OTP — rate-limited to 60s cooldown and 10 per day."""
    if not current_user.phone_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No phone number on file.",
        )

    if current_user.verification_level != "unverified":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone already verified.",
        )

    # Resend is rate-limited
    otp = OTPService.create_otp(db, current_user.phone_number, check_rate_limit=True)

    sms_client = get_sms_client()
    message = f"RentalGuide: {otp.otp_code} — use this to complete your login. Expires in 10 mins."

    result = await sms_client.send_sms(to=current_user.phone_number, message=message)
    sms_sent = bool(result)

    return OTPSendResponse(message="New OTP sent to your registered phone number.", sms_sent=sms_sent)


@router.post("/verify", response_model=OTPVerifyResponse)
async def verify_otp(
    body: OTPVerifyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Verify the OTP. On success upgrades verification_level and returns a fresh JWT."""
    if not current_user.phone_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No phone number on file.",
        )

    if current_user.verification_level != "unverified":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone already verified.",
        )

    ok = OTPService.verify_otp(db, current_user.phone_number, body.code)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP. Please try again.",
        )

    # Upgrade verification level
    current_user.verification_level = "phone_verified"

    # Add phone_verified capability if not already present
    caps = list(current_user.capabilities or [])
    if "phone_verified" not in caps:
        caps.append("phone_verified")
    current_user.capabilities = caps

    db.commit()
    db.refresh(current_user)

    # Issue a fresh JWT reflecting the updated verification level
    access_token = create_access_token(
        data={
            "sub": str(current_user.id),
            "capabilities": current_user.capabilities,
            "verification_level": current_user.verification_level,
        }
    )

    return OTPVerifyResponse(
        message="Phone number verified successfully.",
        verified=True,
        access_token=access_token,
        verification_level=current_user.verification_level,
    )
