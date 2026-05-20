from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.user import User
from app.models.support_ticket import SupportTicket
from app.schemas.support_ticket import (
    SupportTicketCreate,
    SupportTicketResponse,
    SupportTicketListResponse,
)
from app.api.deps import get_current_active_user
from uuid import UUID

router = APIRouter(prefix="/support", tags=["Support"])


@router.post(
    "/tickets",
    response_model=SupportTicketResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_ticket(
    payload: SupportTicketCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    ticket = SupportTicket(
        user_id=current_user.id,
        category=payload.category,
        subject=payload.subject,
        message=payload.message,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


@router.get("/tickets", response_model=SupportTicketListResponse)
async def list_my_tickets(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    total = (
        db.query(SupportTicket)
        .filter(SupportTicket.user_id == current_user.id)
        .count()
    )
    tickets = (
        db.query(SupportTicket)
        .filter(SupportTicket.user_id == current_user.id)
        .order_by(SupportTicket.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return SupportTicketListResponse(tickets=tickets, total=total)


@router.get("/tickets/{ticket_id}", response_model=SupportTicketResponse)
async def get_my_ticket(
    ticket_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    ticket = (
        db.query(SupportTicket)
        .filter(
            SupportTicket.id == ticket_id,
            SupportTicket.user_id == current_user.id,
        )
        .first()
    )
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ticket
