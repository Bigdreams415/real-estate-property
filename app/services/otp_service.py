import random
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.otp import OTPVerification

RESEND_COOLDOWN_SECONDS = 60
DAILY_LIMIT = 10


class OTPService:
    OTP_EXPIRY_MINUTES = 10

    @staticmethod
    def generate_code() -> str:
        return str(random.randint(100000, 999999))

    @staticmethod
    def _check_rate_limit(db: Session, phone: str) -> None:
        now = datetime.utcnow()

        # 60-second cooldown: reject if the most recent OTP was created too recently
        last = (
            db.query(OTPVerification)
            .filter(OTPVerification.phone == phone)
            .order_by(OTPVerification.created_at.desc())
            .first()
        )
        if last and last.created_at:
            elapsed = (now - last.created_at).total_seconds()
            if elapsed < RESEND_COOLDOWN_SECONDS:
                wait = int(RESEND_COOLDOWN_SECONDS - elapsed)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Please wait {wait} seconds before requesting a new code.",
                )

        # Daily limit: max 10 OTPs per phone per 24 hours
        since = now - timedelta(hours=24)
        count = (
            db.query(OTPVerification)
            .filter(
                OTPVerification.phone == phone,
                OTPVerification.created_at >= since,
            )
            .count()
        )
        if count >= DAILY_LIMIT:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many OTP requests today. Please try again tomorrow.",
            )

    @staticmethod
    def create_otp(db: Session, phone: str, check_rate_limit: bool = True) -> OTPVerification:
        if check_rate_limit:
            OTPService._check_rate_limit(db, phone)

        # Invalidate any previous active OTPs for this phone
        db.query(OTPVerification).filter(
            OTPVerification.phone == phone,
            OTPVerification.is_used == False,
        ).update({"is_used": True})

        otp = OTPVerification(
            phone=phone,
            otp_code=OTPService.generate_code(),
            is_used=False,
            expires_at=datetime.utcnow() + timedelta(minutes=OTPService.OTP_EXPIRY_MINUTES),
        )
        db.add(otp)
        db.commit()
        db.refresh(otp)
        return otp

    @staticmethod
    def verify_otp(db: Session, phone: str, code: str) -> bool:
        record = (
            db.query(OTPVerification)
            .filter(
                OTPVerification.phone == phone,
                OTPVerification.otp_code == code.strip(),
                OTPVerification.is_used == False,
                OTPVerification.expires_at > datetime.utcnow(),
            )
            .first()
        )
        if record is None:
            return False
        record.is_used = True
        db.commit()
        return True
