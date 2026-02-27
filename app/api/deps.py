from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.user import User
from app.utils.auth import decode_token
from typing import Optional, List
from uuid import UUID

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)

# Verification level hierarchy
VERIFICATION_LEVELS = {
    "unverified": 0,
    "phone_verified": 1,
    "identity_verified": 2,
    "landlord_verified": 3
}

async def get_current_user(
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(oauth2_scheme)
) -> Optional[User]:
    if not token:
        return None
    
    payload = decode_token(token)
    if not payload:
        return None
    
    user_id = payload.get("sub")
    if not user_id:
        return None
    
    user = db.query(User).filter(User.id == UUID(user_id)).first()
    return user

async def get_current_active_user(
    current_user: Optional[User] = Depends(get_current_user)
) -> User:
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user

def require_capability(required_capability: str):
    async def capability_checker(
        current_user: User = Depends(get_current_active_user)
    ):
        if required_capability not in current_user.capabilities:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required capability: {required_capability}"
            )
        return current_user
    return capability_checker

def require_any_capability(required_capabilities: List[str]):
    async def capability_checker(
        current_user: User = Depends(get_current_active_user)
    ):
        user_caps = set(current_user.capabilities)
        if not any(cap in user_caps for cap in required_capabilities):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required capability. Need one of: {required_capabilities}"
            )
        return current_user
    return capability_checker

def require_verification_level(min_level: str):
    async def verification_checker(
        current_user: User = Depends(get_current_active_user)
    ):
        user_level = VERIFICATION_LEVELS.get(current_user.verification_level, 0)
        required_level = VERIFICATION_LEVELS.get(min_level, 0)
        
        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Verification level too low. Required: {min_level}"
            )
        return current_user
    return verification_checker