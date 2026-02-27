from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.user import User
from app.utils.auth import verify_password, create_access_token

router = APIRouter(tags=["Admin Auth"])


@router.post("/auth/token")
async def admin_login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Admin-only login. Rejects any user who doesn't have 'admin_access' capability.
    Used by the React admin dashboard.
    """
    user = db.query(User).filter(User.email == form_data.username).first()

    # Generic error — don't reveal whether email exists or not
    auth_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials or insufficient permissions",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not user or not verify_password(form_data.password, user.password_hash):
        raise auth_error

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account is deactivated",
        )

    # ── This is the key check — regular users are blocked here ───────────────
    if "admin_access" not in (user.capabilities or []):
        raise auth_error

    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "capabilities": user.capabilities,
            "verification_level": user.verification_level,
        }
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "full_name": user.full_name,
            "email": user.email,
            "capabilities": user.capabilities,
        },
    }