from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_db
from app.models.user import User
from app.models.property import Property
from app.models.favorite import Favorite
from app.schemas.user import UserCreate, UserLogin, TokenResponse, UserResponse
from app.utils.auth import get_password_hash, verify_password, create_access_token
from app.api.deps import get_current_active_user
from datetime import timedelta
from app.core.config import settings

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
        address=user_data.address
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