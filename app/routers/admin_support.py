from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_admin_user
from app.core.database import get_db
from app.models.support_ticket import SupportTicket
from app.models.user import User
from app.schemas.support_ticket import (
    AdminTicketListResponse,
    AdminTicketResponse,
    SupportTicketAdminUpdate,
)
from app.services import fcm_service

router = APIRouter(prefix="/support", tags=["Admin Support"])


def _build_admin_response(ticket: SupportTicket) -> AdminTicketResponse:
    user = ticket.user
    return AdminTicketResponse(
        id=ticket.id,
        user_id=ticket.user_id,
        category=ticket.category,
        subject=ticket.subject,
        message=ticket.message,
        status=ticket.status,
        admin_reply=ticket.admin_reply,
        replied_at=ticket.replied_at,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        user_email=user.email if user else "",
        user_full_name=user.full_name if user else "",
    )


@router.get("/tickets", response_model=AdminTicketListResponse)
async def list_all_tickets(
    ticket_status: str | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    q = db.query(SupportTicket).options(joinedload(SupportTicket.user))
    if ticket_status:
        q = q.filter(SupportTicket.status == ticket_status)
    total = q.count()
    tickets = q.order_by(SupportTicket.created_at.desc()).offset(skip).limit(limit).all()
    return AdminTicketListResponse(
        tickets=[_build_admin_response(t) for t in tickets],
        total=total,
    )


@router.get("/tickets/{ticket_id}", response_model=AdminTicketResponse)
async def get_ticket(
    ticket_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    ticket = (
        db.query(SupportTicket)
        .options(joinedload(SupportTicket.user))
        .filter(SupportTicket.id == ticket_id)
        .first()
    )
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return _build_admin_response(ticket)


@router.patch("/tickets/{ticket_id}", response_model=AdminTicketResponse)
async def update_ticket(
    ticket_id: UUID,
    payload: SupportTicketAdminUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    ticket = (
        db.query(SupportTicket)
        .options(joinedload(SupportTicket.user))
        .filter(SupportTicket.id == ticket_id)
        .first()
    )
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    if payload.status is not None:
        ticket.status = payload.status
    if payload.admin_reply is not None:
        ticket.admin_reply = payload.admin_reply
        ticket.replied_at = datetime.now(timezone.utc)

    ticket.handled_by = admin.id
    db.commit()
    db.refresh(ticket)

    status_label = ticket.status.replace("_", " ")
    background_tasks.add_task(
        fcm_service.send_to_user,
        db,
        ticket.user_id,
        "Support ticket update",
        f'Your ticket "{ticket.subject}" is now {status_label}.',
        {"screen": "ticket-detail", "id": str(ticket.id)},
        "support",
    )

    return _build_admin_response(ticket)
