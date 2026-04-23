from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List
from uuid import UUID

from app.core.database import get_db
from app.models.inspection import Inspection, InspectionStatus
from app.models.property import Property
from app.models.user import User
from app.schemas.inspection import InspectionRequest, InspectionReschedule, InspectionResponse
from app.api.deps import get_current_active_user

router = APIRouter(prefix="/inspections", tags=["Inspections"])


@router.post("/", response_model=InspectionResponse, status_code=status.HTTP_201_CREATED)
async def request_inspection(
    payload: InspectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Requester schedules an inspection for a property."""

    prop = db.query(Property).filter(Property.id == payload.property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found.")

    if str(prop.owner_id) == str(current_user.id):
        raise HTTPException(
            status_code=400,
            detail="You cannot request an inspection for your own property.",
        )

    # Prevent duplicate pending inspection for same user + property
    existing = (
        db.query(Inspection)
        .filter(
            Inspection.property_id == payload.property_id,
            Inspection.requester_id == current_user.id,
            Inspection.status.in_([
                InspectionStatus.PENDING,
                InspectionStatus.CONFIRMED,
                InspectionStatus.RESCHEDULED,
            ]),
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail="You already have an active inspection request for this property.",
        )

    inspection = Inspection(
        property_id=payload.property_id,
        requester_id=current_user.id,
        owner_id=prop.owner_id,
        requested_date=payload.requested_date,
        requester_note=payload.requester_note,
        status=InspectionStatus.PENDING,
    )

    db.add(inspection)
    db.commit()
    db.refresh(inspection)
    return inspection


@router.get("/mine", response_model=List[InspectionResponse])
async def get_my_inspections(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    status_filter: str = Query(None),
):
    """Get all inspections where current user is requester or owner."""

    query = db.query(Inspection).filter(
        or_(
            Inspection.requester_id == current_user.id,
            Inspection.owner_id == current_user.id,
        )
    )

    if status_filter:
        try:
            query = query.filter(
                Inspection.status == InspectionStatus(status_filter)
            )
        except ValueError:
            pass

    inspections = query.order_by(Inspection.created_at.desc()).all()
    return inspections


@router.post("/{inspection_id}/confirm", response_model=InspectionResponse)
async def confirm_inspection(
    inspection_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Owner confirms the inspection at the requested date."""

    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found.")

    if str(inspection.owner_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Only the property owner can confirm.")

    if inspection.status not in [InspectionStatus.PENDING, InspectionStatus.RESCHEDULED]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot confirm an inspection with status '{inspection.status}'.",
        )

    inspection.status = InspectionStatus.CONFIRMED
    inspection.confirmed_date = inspection.requested_date
    db.commit()
    db.refresh(inspection)
    return inspection


@router.post("/{inspection_id}/reschedule", response_model=InspectionResponse)
async def reschedule_inspection(
    inspection_id: UUID,
    payload: InspectionReschedule,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Owner proposes a new date instead of confirming the original."""

    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found.")

    if str(inspection.owner_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Only the property owner can reschedule.")

    if inspection.status not in [InspectionStatus.PENDING, InspectionStatus.RESCHEDULED]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reschedule an inspection with status '{inspection.status}'.",
        )

    inspection.status = InspectionStatus.RESCHEDULED
    inspection.confirmed_date = payload.confirmed_date
    inspection.owner_note = payload.owner_note
    db.commit()
    db.refresh(inspection)
    return inspection


@router.post("/{inspection_id}/cancel", response_model=InspectionResponse)
async def cancel_inspection(
    inspection_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Either party can cancel an inspection."""

    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found.")

    is_requester = str(inspection.requester_id) == str(current_user.id)
    is_owner = str(inspection.owner_id) == str(current_user.id)

    if not is_requester and not is_owner:
        raise HTTPException(status_code=403, detail="Not your inspection.")

    if inspection.status in [InspectionStatus.COMPLETED, InspectionStatus.CANCELLED]:
        raise HTTPException(
            status_code=400,
            detail=f"Inspection is already {inspection.status}.",
        )

    inspection.status = InspectionStatus.CANCELLED
    db.commit()
    db.refresh(inspection)
    return inspection


@router.post("/{inspection_id}/complete", response_model=InspectionResponse)
async def complete_inspection(
    inspection_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Either party marks the inspection as completed after it happens."""

    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found.")

    is_requester = str(inspection.requester_id) == str(current_user.id)
    is_owner = str(inspection.owner_id) == str(current_user.id)

    if not is_requester and not is_owner:
        raise HTTPException(status_code=403, detail="Not your inspection.")

    if inspection.status != InspectionStatus.CONFIRMED:
        raise HTTPException(
            status_code=400,
            detail="Only confirmed inspections can be marked as completed.",
        )

    inspection.status = InspectionStatus.COMPLETED
    db.commit()
    db.refresh(inspection)
    return inspection