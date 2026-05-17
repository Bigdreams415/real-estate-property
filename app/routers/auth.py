from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_db
from app.models.user import User
from app.models.property import Property
from app.models.favorite import Favorite
from app.schemas.user import (
    UserCreate, UserLogin, TokenResponse, UserResponse,
    GoogleAuthRequest, CompleteProfileRequest,
)
from app.utils.auth import get_password_hash, verify_password, create_access_token
from app.api.deps import get_current_active_user
from datetime import timedelta
from app.core.config import settings
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    # Check if email exists
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Check if phone exists
    if db.query(User).filter(User.phone_number == user_data.phone_number).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number already registered"
        )
    
    # Create new user with default capabilities
    user = User(
        email=user_data.email,
        phone_number=user_data.phone_number,
        full_name=user_data.full_name,
        password_hash=get_password_hash(user_data.password),
        capabilities=["browse_properties", "save_favorites"],
        verification_level="unverified",
        city=user_data.city,
        state=user_data.state,
        lga=user_data.lga,
        address=user_data.address,
        auth_provider="local",
        is_profile_complete=True,
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Create token with capabilities in payload
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "capabilities": user.capabilities,
            "verification_level": user.verification_level
        }
    )
    
    return TokenResponse(
        access_token=access_token,
        user=UserResponse.model_validate(user)
    )

@router.post("/login", response_model=TokenResponse)
async def login(user_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_data.email).first()
    
    if not user or not verify_password(user_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account is deactivated"
        )
    
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "capabilities": user.capabilities,
            "verification_level": user.verification_level
        }
    )
    
    return TokenResponse(
        access_token=access_token,
        user=UserResponse.model_validate(user)
    )

@router.post("/token", response_model=dict)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """OAuth2 compatible token endpoint for Swagger UI"""
    user = db.query(User).filter(User.email == form_data.username).first()
    
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account is deactivated"
        )
    
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "capabilities": user.capabilities,
            "verification_level": user.verification_level
        }
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
):
    return current_user


@router.get("/me/stats")
async def get_user_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Returns aggregate stats for the authenticated user's profile."""
    total_listings = (
        db.query(func.count(Property.id))
        .filter(Property.owner_id == current_user.id)
        .scalar()
    )

    total_views = (
        db.query(func.coalesce(func.sum(Property.view_count), 0))
        .filter(Property.owner_id == current_user.id)
        .scalar()
    )

    favorites_count = (
        db.query(func.count(Favorite.id))
        .filter(Favorite.user_id == current_user.id)
        .scalar()
    )

    return {
        "total_listings": total_listings,
        "total_views": total_views,
        "favorites_count": favorites_count,
    }


@router.post("/google", response_model=TokenResponse)
async def google_auth(request: GoogleAuthRequest, db: Session = Depends(get_db)):
    """Sign in or register with a Google ID token from the mobile app."""
    # Verify token with Google (no audience — we check manually to support Android/iOS/Web)
    try:
        claims = google_id_token.verify_oauth2_token(
            request.id_token,
            google_requests.Request(),
            audience=None,
        )
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google token")

    # Validate the audience is one of our registered client IDs
    token_aud = claims.get("aud", "")
    valid_clients = {
        settings.GOOGLE_CLIENT_ID_ANDROID,
        settings.GOOGLE_CLIENT_ID_IOS,
        settings.GOOGLE_CLIENT_ID_WEB,
    } - {""}  # remove empty strings (unconfigured platforms)

    if valid_clients and token_aud not in valid_clients:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token audience mismatch")

    google_sub = claims["sub"]
    email = claims.get("email", "")
    full_name = claims.get("name", "")
    picture = claims.get("picture")

    # Look up existing user: first by google_sub, then by email (account linking)
    user = db.query(User).filter(User.google_sub == google_sub).first()
    if user is None and email:
        user = db.query(User).filter(User.email == email).first()
        if user:
            # Link this Google account to the existing local account
            user.google_sub = google_sub
            user.auth_provider = "google"
            if picture and not user.profile_image:
                user.profile_image = picture
            db.commit()
            db.refresh(user)

    if user is None:
        # Brand new user — create partial record; profile completion required
        user = User(
            email=email,
            full_name=full_name,
            profile_image=picture,
            auth_provider="google",
            google_sub=google_sub,
            capabilities=["browse_properties", "save_favorites"],
            verification_level="unverified",
            is_profile_complete=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account is deactivated")

    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "capabilities": user.capabilities,
            "verification_level": user.verification_level,
        }
    )
    return TokenResponse(access_token=access_token, user=UserResponse.model_validate(user))


@router.patch("/me/complete-profile", response_model=UserResponse)
async def complete_profile(
    data: CompleteProfileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Collect phone + address for users who signed up via Google (Step 2)."""
    if current_user.is_profile_complete:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Profile already completed")

    # Phone uniqueness check
    existing = db.query(User).filter(
        User.phone_number == data.phone_number,
        User.id != current_user.id,
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Phone number already registered")

    current_user.phone_number = data.phone_number
    current_user.city = data.city
    current_user.state = data.state
    current_user.lga = data.lga
    current_user.address = data.address
    current_user.is_profile_complete = True

    db.commit()
    db.refresh(current_user)
    return UserResponse.model_validate(current_user)


@router.delete("/me")
async def delete_account(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Permanently delete the authenticated user's account and all associated data."""
    # Delete related records first (cascade manually for safety)
    from app.models.favorite import Favorite
    from app.models.inspection import Inspection

    db.query(Favorite).filter(Favorite.user_id == current_user.id).delete()
    db.query(Inspection).filter(Inspection.requester_id == current_user.id).delete()
    db.query(Inspection).filter(Inspection.owner_id == current_user.id).delete()

    # Delete user properties and their images/videos (cascade in model handles children)
    db.query(Property).filter(Property.owner_id == current_user.id).delete()

    db.delete(current_user)
    db.commit()
    return {"message": "Account deleted successfully"}