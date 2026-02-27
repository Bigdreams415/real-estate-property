import json
from fastapi import APIRouter, Depends, HTTPException, status, Query, Form, UploadFile, File
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, case, Integer, literal, func, String
from datetime import datetime
from app.core.database import get_db
from app.models.property import (
    Property, PropertyType, ListingType, PropertyStatus,
    PropertyVerificationStatus, PropertyImage, PropertyVideo
)
from app.models.user import User
from app.schemas.property import (
    PropertyResponse, PropertyVerificationAction, OwnershipDocument
)
from app.api.deps import get_current_user, get_current_active_user, require_capability
from app.utils.file_storage import save_property_images, delete_property_image
from typing import List, Optional
from uuid import UUID

router = APIRouter(prefix="/properties", tags=["Properties"])


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _normalize_property(prop: Property):
    """Ensure JSON/list fields are not None so response validation passes."""
    if getattr(prop, "ownership_documents", None) is None:
        prop.ownership_documents = []
    return prop


def _parse_verification_document(raw: str) -> List[OwnershipDocument]:
    """
    Parse the 'verification_document' JSON string sent from the Flutter form.
    Accepts either a single dict or a list of dicts.
    Returns a list of validated OwnershipDocument objects.
    """
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="'verification_document' must be a valid JSON string.",
        )

    if isinstance(parsed, dict):
        parsed = [parsed]

    if not isinstance(parsed, list):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="'verification_document' must be a JSON object or array.",
        )

    try:
        return [OwnershipDocument(**doc) for doc in parsed]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid document structure: {str(e)}",
        )


def _parse_features(raw: Optional[str]) -> List[str]:
    """Parse the 'features' JSON array string. Returns [] on failure."""
    if not raw:
        return []
    try:
        result = json.loads(raw)
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _parse_captions(raw: Optional[str]) -> List[str]:
    """Parse the 'image_captions' JSON array string. Returns [] on failure."""
    if not raw:
        return []
    try:
        result = json.loads(raw)
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


# ─── CREATE: Multipart form + image uploads ───────────────────────────────────

@router.post("/", response_model=PropertyResponse, status_code=status.HTTP_201_CREATED)
async def create_property(
    # ── Required text fields ──────────────────────────────────────────────────
    title: str = Form(...),
    description: str = Form(...),
    property_type: PropertyType = Form(...),
    listing_type: ListingType = Form(...),
    address: str = Form(...),
    city: str = Form(...),
    state: str = Form(...),
    lga: str = Form(...),
    price: float = Form(...),

    # ── Optional text fields ──────────────────────────────────────────────────
    landmark: Optional[str] = Form(None),
    bedrooms: Optional[int] = Form(None),
    bathrooms: Optional[int] = Form(None),
    toilets: Optional[int] = Form(None),
    square_meters: Optional[float] = Form(None),
    plot_size: Optional[str] = Form(None),

    # ── JSON-encoded string fields (serialised on the Flutter side) ───────────
    features: Optional[str] = Form(None),             # JSON array of strings
    image_captions: Optional[str] = Form(None),       # JSON array of caption strings
    verification_document: str = Form(...),           # JSON object (single doc)
    video_url: Optional[str] = Form(None),            # plain URL string (YouTube/Vimeo)

    # ── Image files ───────────────────────────────────────────────────────────
    images: List[UploadFile] = File(...),

    # ── Auth / DB ─────────────────────────────────────────────────────────────
    db: Session = Depends(get_db),
    current_user: User = Depends(require_capability("create_listing")),
):
    """
    Create a new property listing.
    Accepts multipart/form-data with real image file uploads.
    Videos are stored as external URLs only (YouTube / Vimeo).
    """

    # ── Validate images ───────────────────────────────────────────────────────
    if not images:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one property image is required.",
        )

    # ── Parse & validate ownership document ───────────────────────────────────
    ownership_docs = _parse_verification_document(verification_document)
    if not ownership_docs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one ownership document is required.",
        )

    # ── Parse optional JSON strings ───────────────────────────────────────────
    parsed_features = _parse_features(features)
    parsed_captions = _parse_captions(image_captions)

    # ── Save uploaded image files to disk ─────────────────────────────────────
    # Returns list of public URLs in the same order as the uploaded files
    try:
        image_urls = await save_property_images(images)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save images: {str(e)}",
        )

    # ── Persist property ──────────────────────────────────────────────────────
    property_obj = Property(
        title=title,
        description=description,
        property_type=property_type,
        listing_type=listing_type,
        address=address,
        city=city,
        state=state,
        lga=lga,
        landmark=landmark,
        price=price,
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        toilets=toilets,
        square_meters=square_meters,
        plot_size=plot_size,
        features=parsed_features,
        owner_id=current_user.id,
        # Store documents as a list of dicts (JSON column)
        ownership_documents=[doc.model_dump() for doc in ownership_docs],
        main_image=image_urls[0] if image_urls else None,
        verification_status=PropertyVerificationStatus.PENDING_VERIFICATION,
        status=PropertyStatus.PENDING,
    )

    db.add(property_obj)
    db.flush()  # get property_obj.id before adding children

    # ── Add PropertyImage rows ────────────────────────────────────────────────
    for idx, url in enumerate(image_urls):
        caption = parsed_captions[idx] if idx < len(parsed_captions) else None
        db.add(PropertyImage(
            property_id=property_obj.id,
            image_url=url,
            is_main=(idx == 0),
            caption=caption or None,
            display_order=idx,
        ))

    # ── Add PropertyVideo row (if a URL was provided) ─────────────────────────
    if video_url and video_url.strip():
        db.add(PropertyVideo(
            property_id=property_obj.id,
            video_url=video_url.strip(),
            display_order=0,
        ))

    db.commit()
    db.refresh(property_obj)
    _normalize_property(property_obj)

    return property_obj


# ─── UPDATE: also multipart (images re-uploaded on edit) ──────────────────────

@router.put("/{property_id}", response_model=PropertyResponse)
async def update_property(
    property_id: UUID,

    title: str = Form(...),
    description: str = Form(...),
    property_type: PropertyType = Form(...),
    listing_type: ListingType = Form(...),
    address: str = Form(...),
    city: str = Form(...),
    state: str = Form(...),
    lga: str = Form(...),
    price: float = Form(...),

    landmark: Optional[str] = Form(None),
    bedrooms: Optional[int] = Form(None),
    bathrooms: Optional[int] = Form(None),
    toilets: Optional[int] = Form(None),
    square_meters: Optional[float] = Form(None),
    plot_size: Optional[str] = Form(None),

    features: Optional[str] = Form(None),
    image_captions: Optional[str] = Form(None),
    verification_document: Optional[str] = Form(None),
    video_url: Optional[str] = Form(None),

    # Images are optional on update — omit to keep existing images
    images: Optional[List[UploadFile]] = File(None),

    db: Session = Depends(get_db),
    current_user: User = Depends(require_capability("create_listing")),
):
    """Update a property. Re-upload images to replace them, or omit to keep existing."""

    prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found.")

    is_admin = "admin_access" in current_user.capabilities
    if prop.owner_id != current_user.id and not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only update your own properties.")

    # ── Basic fields ──────────────────────────────────────────────────────────
    prop.title = title
    prop.description = description
    prop.property_type = property_type
    prop.listing_type = listing_type
    prop.address = address
    prop.city = city
    prop.state = state
    prop.lga = lga
    prop.landmark = landmark
    prop.price = price
    prop.bedrooms = bedrooms
    prop.bathrooms = bathrooms
    prop.toilets = toilets
    prop.square_meters = square_meters
    prop.plot_size = plot_size
    prop.features = _parse_features(features)

    # ── Ownership documents ───────────────────────────────────────────────────
    if verification_document:
        ownership_docs = _parse_verification_document(verification_document)
        prop.ownership_documents = [doc.model_dump() for doc in ownership_docs]
        # Reset verification so admin re-reviews
        prop.verification_status = PropertyVerificationStatus.PENDING_VERIFICATION
        prop.status = PropertyStatus.PENDING

    # ── Images (only replace if new files provided) ───────────────────────────
    real_images = [f for f in (images or []) if f and f.filename]
    if real_images:
        # Delete old files from disk
        old_images = db.query(PropertyImage).filter(PropertyImage.property_id == property_id).all()
        for old in old_images:
            delete_property_image(old.image_url)
        db.query(PropertyImage).filter(PropertyImage.property_id == property_id).delete()

        image_urls = await save_property_images(real_images)
        parsed_captions = _parse_captions(image_captions)

        prop.main_image = image_urls[0]
        for idx, url in enumerate(image_urls):
            caption = parsed_captions[idx] if idx < len(parsed_captions) else None
            db.add(PropertyImage(
                property_id=prop.id,
                image_url=url,
                is_main=(idx == 0),
                caption=caption or None,
                display_order=idx,
            ))

    # ── Video ─────────────────────────────────────────────────────────────────
    if video_url is not None:
        db.query(PropertyVideo).filter(PropertyVideo.property_id == property_id).delete()
        if video_url.strip():
            db.add(PropertyVideo(
                property_id=prop.id,
                video_url=video_url.strip(),
                display_order=0,
            ))

    db.commit()
    db.refresh(prop)
    _normalize_property(prop)
    return prop


# ─── LIST (public) ────────────────────────────────────────────────────────────

@router.get("/", response_model=List[PropertyResponse])
async def list_properties(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, min_length=2),
    state: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    property_type: Optional[PropertyType] = Query(None),
    listing_type: Optional[ListingType] = Query(None),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    bedrooms: Optional[int] = Query(None),
    sort_by: Optional[str] = Query("newest", pattern="^(newest|oldest|price_low|price_high|relevance|most_viewed)$"),
    show_pending: bool = Query(False),
):
    """List verified properties with filtering and sorting."""

    query = db.query(Property).filter(
        func.lower(Property.status.cast(String)) == PropertyStatus.AVAILABLE.value,
        func.lower(Property.verification_status.cast(String)) == PropertyVerificationStatus.VERIFIED.value,
    )

    if show_pending and current_user:
        query = db.query(Property).filter(
            or_(
                and_(
                    func.lower(Property.status.cast(String)) == PropertyStatus.AVAILABLE.value,
                    func.lower(Property.verification_status.cast(String)) == PropertyVerificationStatus.VERIFIED.value,
                ),
                and_(
                    Property.owner_id == current_user.id,
                    func.lower(Property.verification_status.cast(String)).in_([
                        PropertyVerificationStatus.PENDING_VERIFICATION.value,
                        PropertyVerificationStatus.REJECTED.value,
                    ]),
                ),
            )
        )

    if search:
        search_term = f"%{search}%"
        relevance = (
            case((Property.title.ilike(f"%{search}%"), 10), else_=0).cast(Integer)
            + case((Property.address.ilike(search_term), 8), else_=0).cast(Integer)
            + case((Property.city.ilike(search_term), 7), else_=0).cast(Integer)
            + case((Property.state.ilike(search_term), 6), else_=0).cast(Integer)
            + case((Property.landmark.ilike(search_term), 5), else_=0).cast(Integer)
            + case((Property.lga.ilike(search_term), 4), else_=0).cast(Integer)
            + case((Property.description.ilike(search_term), 3), else_=0).cast(Integer)
        ).label("relevance")

        query = query.filter(
            or_(
                Property.title.ilike(search_term),
                Property.description.ilike(search_term),
                Property.address.ilike(search_term),
                Property.city.ilike(search_term),
                Property.state.ilike(search_term),
                Property.landmark.ilike(search_term),
                Property.lga.ilike(search_term),
            )
        )
        query = query.add_columns(relevance)
    else:
        query = query.add_columns(literal(0).label("relevance"))

    if state:
        query = query.filter(Property.state.ilike(f"%{state}%"))
    if city:
        query = query.filter(Property.city.ilike(f"%{city}%"))
    if property_type:
        query = query.filter(Property.property_type == property_type)
    if listing_type:
        query = query.filter(Property.listing_type == listing_type)
    if min_price is not None:
        query = query.filter(Property.price >= min_price)
    if max_price is not None:
        query = query.filter(Property.price <= max_price)
    if bedrooms is not None and bedrooms > 0:
        query = query.filter(Property.bedrooms >= bedrooms)

    if search and sort_by == "relevance":
        query = query.order_by(literal("relevance").desc(), Property.created_at.desc())
    elif sort_by == "oldest":
        query = query.order_by(Property.created_at.asc())
    elif sort_by == "price_low":
        query = query.order_by(Property.price.asc())
    elif sort_by == "price_high":
        query = query.order_by(Property.price.desc())
    elif sort_by == "most_viewed":
        query = query.order_by(Property.view_count.desc())
    else:
        query = query.order_by(Property.created_at.desc())

    results = query.offset(skip).limit(limit).all()
    properties = [r[0] for r in results]
    for p in properties:
        _normalize_property(p)
    return properties


# ─── ADMIN: list pending ──────────────────────────────────────────────────────

@router.get("/admin/pending", response_model=List[PropertyResponse])
async def list_pending_properties(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_capability("admin_access")),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    """List all pending-verification properties. Admin only."""
    properties = (
        db.query(Property)
        .filter(Property.verification_status == PropertyVerificationStatus.PENDING_VERIFICATION)
        .order_by(Property.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    for p in properties:
        _normalize_property(p)
    return properties


# ─── ADMIN: approve / reject ──────────────────────────────────────────────────

@router.post("/admin/{property_id}/verify", response_model=PropertyResponse)
async def verify_property(
    property_id: UUID,
    verification_action: PropertyVerificationAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_capability("admin_access")),
):
    """Approve or reject a property listing. Admin only."""
    prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found.")

    if prop.verification_status != PropertyVerificationStatus.PENDING_VERIFICATION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Property is already {prop.verification_status.value}.",
        )

    if verification_action.action not in ("approve", "reject"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Action must be 'approve' or 'reject'.",
        )

    if verification_action.action == "approve":
        prop.verification_status = PropertyVerificationStatus.VERIFIED
        prop.status = PropertyStatus.AVAILABLE
    else:
        prop.verification_status = PropertyVerificationStatus.REJECTED
        prop.status = PropertyStatus.UNAVAILABLE

    prop.verified_by = current_user.id
    prop.verified_at = datetime.utcnow()
    prop.verification_notes = verification_action.notes or (
        None if verification_action.action == "approve"
        else "Ownership documents did not meet verification requirements."
    )

    db.commit()
    db.refresh(prop)
    _normalize_property(prop)
    return prop


# ─── GET single property (public) ────────────────────────────────────────────

@router.get("/{property_id}", response_model=PropertyResponse)
async def get_property(
    property_id: UUID,
    db: Session = Depends(get_db),
):
    """Get a single property. Public — no auth required. Increments view count."""
    prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found.")

    prop.view_count += 1
    db.commit()
    db.refresh(prop)
    _normalize_property(prop)
    return prop