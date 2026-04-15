from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.user import User
from app.api.deps import get_current_active_user

router = APIRouter(prefix="/favorites", tags=["Favorites"])


@router.get("/count")
async def get_favorites_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Returns the number of properties the current user has favorited.
    Returns 0 for now — expand this when the favorites feature is built.
    """
    # TODO: when you build the Favorite model, replace this with:
    # count = db.query(Favorite).filter(Favorite.user_id == current_user.id).count()
    return {"count": 0}