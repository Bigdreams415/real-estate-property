from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_
from uuid import UUID
from app.core.database import get_db
from app.models.user import User
from app.models.property import Property
from app.models.favorite import Favorite
from app.schemas.favorite import (
    FavoriteResponse,
    FavoriteWithProperty,
    FavoriteListResponse,
    FavoriteActionResponse,
)
from app.api.deps import get_current_active_user

router = APIRouter(prefix="/favorites", tags=["Favorites"])


def _build_favorite_with_property(fav: Favorite) -> FavoriteWithProperty:
    prop = fav.property
    return FavoriteWithProperty(
        id=fav.id,
        user_id=fav.user_id,
        property_id=fav.property_id,
        created_at=fav.created_at,
        property_title=prop.title if prop else None,
        property_image=prop.main_image if prop else None,
        property_price=prop.price if prop else None,
        property_city=prop.city if prop else None,
        property_state=prop.state if prop else None,
        property_type=prop.property_type.value if prop and prop.property_type else None,
        listing_type=prop.listing_type.value if prop and prop.listing_type else None,
        view_count=prop.view_count if prop else None,
        status=prop.status.value if prop and prop.status else None,
    )


@router.get("/", response_model=FavoriteListResponse)
async def list_favorites(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List the current user's favorited properties with property details."""
    total = (
        db.query(Favorite)
        .filter(Favorite.user_id == current_user.id)
        .count()
    )

    favorites = (
        db.query(Favorite)
        .filter(Favorite.user_id == current_user.id)
        .order_by(Favorite.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return FavoriteListResponse(
        favorites=[_build_favorite_with_property(f) for f in favorites],
        total=total,
    )


@router.get("/count")
async def get_favorites_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Returns the number of properties the current user has favorited."""
    count = (
        db.query(Favorite)
        .filter(Favorite.user_id == current_user.id)
        .count()
    )
    return {"count": count}


@router.post("/{property_id}", response_model=FavoriteActionResponse, status_code=status.HTTP_201_CREATED)
async def add_favorite(
    property_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Add a property to the current user's favorites."""
    prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found",
        )

    existing = (
        db.query(Favorite)
        .filter(
            and_(
                Favorite.user_id == current_user.id,
                Favorite.property_id == property_id,
            )
        )
        .first()
    )
    if existing:
        return FavoriteActionResponse(message="Property already in favorites", is_favorited=True)

    fav = Favorite(user_id=current_user.id, property_id=property_id)
    db.add(fav)
    db.commit()

    return FavoriteActionResponse(message="Added to favorites", is_favorited=True)


@router.delete("/{property_id}", response_model=FavoriteActionResponse)
async def remove_favorite(
    property_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Remove a property from the current user's favorites."""
    fav = (
        db.query(Favorite)
        .filter(
            and_(
                Favorite.user_id == current_user.id,
                Favorite.property_id == property_id,
            )
        )
        .first()
    )
    if not fav:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Favorite not found",
        )

    db.delete(fav)
    db.commit()

    return FavoriteActionResponse(message="Removed from favorites", is_favorited=False)


@router.get("/check/{property_id}")
async def check_favorite(
    property_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Check if a property is favorited by the current user."""
    fav = (
        db.query(Favorite)
        .filter(
            and_(
                Favorite.user_id == current_user.id,
                Favorite.property_id == property_id,
            )
        )
        .first()
    )
    return {"is_favorited": fav is not None}
