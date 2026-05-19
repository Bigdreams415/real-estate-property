from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.core.database import get_db
from app.models.user import User
from app.models.device_token import DeviceToken
from app.api.deps import get_verified_user

router = APIRouter(prefix="/notifications", tags=["Notifications"])


class RegisterTokenRequest(BaseModel):
    token: str
    platform: str  # "android" or "ios"


class RemoveTokenRequest(BaseModel):
    token: str


@router.post("/register-token", status_code=status.HTTP_200_OK)
def register_token(
    body: RegisterTokenRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_verified_user),
):
    """Register or refresh an FCM device token for the current user."""
    if body.platform not in ("android", "ios"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="platform must be 'android' or 'ios'",
        )

    existing = db.query(DeviceToken).filter(DeviceToken.token == body.token).first()

    if existing:
        # Token already registered — update owner if it changed (device handed to new user)
        if existing.user_id != current_user.id:
            existing.user_id = current_user.id
            existing.platform = body.platform
            db.commit()
    else:
        db.add(DeviceToken(
            user_id=current_user.id,
            token=body.token,
            platform=body.platform,
        ))
        db.commit()

    return {"message": "Token registered"}


@router.post("/remove-token", status_code=status.HTTP_200_OK)
def remove_token(
    body: RemoveTokenRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_verified_user),
):
    """Remove an FCM token (call this on logout so the device stops receiving notifications)."""
    db.query(DeviceToken).filter(
        DeviceToken.token == body.token,
        DeviceToken.user_id == current_user.id,
    ).delete()
    db.commit()
    return {"message": "Token removed"}
