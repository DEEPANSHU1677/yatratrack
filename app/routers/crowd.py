from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_roles
from app.database import get_db
from app.models import models
from app.schemas import schemas
from app.services import crowd_service

router = APIRouter(prefix="/crowd", tags=["Crowd Reporting"])


@router.post("/report")
def report_crowd(
    payload: schemas.CrowdReportCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    trip = db.query(models.Trip).filter(models.Trip.id == payload.trip_id).first()
    if not trip:
        raise HTTPException(404, "Trip not found")

    if payload.ticket_id:
        ticket = db.query(models.Ticket).filter(models.Ticket.id == payload.ticket_id).first()
        if not ticket or ticket.trip_id != trip.id or ticket.passenger_id != current_user.id:
            raise HTTPException(403, "Ticket does not belong to this trip/user")
    elif current_user.role not in (models.UserRole.CONDUCTOR, models.UserRole.OPERATOR, models.UserRole.ADMIN):
        raise HTTPException(400, "Passenger crowd reports require ticket_id")
    elif current_user.role == models.UserRole.CONDUCTOR and current_user.assigned_bus_id != trip.bus_id:
        raise HTTPException(403, "You are not assigned to this bus")

    # One active passenger report per ticket; updating it prevents vote spamming.
    report = None
    if payload.ticket_id:
        report = db.query(models.CrowdReport).filter(
            models.CrowdReport.trip_id == trip.id,
            models.CrowdReport.ticket_id == payload.ticket_id,
        ).order_by(models.CrowdReport.reported_at.desc()).first()
    if report:
        report.level = payload.level
        from datetime import datetime
        report.reported_at = datetime.utcnow()
    else:
        report = models.CrowdReport(trip_id=trip.id, ticket_id=payload.ticket_id, level=payload.level)
        db.add(report)
    db.commit()
    return {"message": "Crowd report recorded"}


@router.get("/trip/{trip_id}", response_model=schemas.CrowdStatusOut)
def get_crowd(trip_id: str, db: Session = Depends(get_db)):
    if not db.query(models.Trip).filter(models.Trip.id == trip_id).first():
        raise HTTPException(404, "Trip not found")
    result = crowd_service.get_crowd_status(db, trip_id)
    if not result:
        raise HTTPException(404, "No recent crowd reports yet for this trip")
    return result


@router.get("/trip/{trip_id}/predict")
def predict_crowd(trip_id: str, from_stop_sequence: int, db: Session = Depends(get_db)):
    return crowd_service.predict_crowd_at_stop(db, trip_id, from_stop_sequence)
