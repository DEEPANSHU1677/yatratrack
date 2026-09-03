from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.auth import ALGORITHM, SECRET_KEY, get_current_user
from app.database import get_db
from app.models import models
from app.schemas import schemas
from app.services import crowd_service, eta_service, gps_aggregation_service

router = APIRouter(prefix="/gps", tags=["Live Tracking"])


def _decode_optional_user(authorization: Optional[str], db: Session):
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        payload = jwt.decode(authorization.split(" ", 1)[1], SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
    except JWTError:
        return None
    return db.query(models.User).filter(models.User.id == user_id).first()


@router.post("/ping")
def report_location(
    payload: schemas.GPSPingCreate,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    trip = db.query(models.Trip).filter(models.Trip.id == payload.trip_id).first()
    if not trip:
        raise HTTPException(404, "Trip not found")
    if trip.status == models.TripStatus.CANCELLED:
        raise HTTPException(409, "Cannot report location for a cancelled trip")

    ticket = None
    if payload.source == "passenger":
        user = _decode_optional_user(authorization, db)
        if not user:
            raise HTTPException(401, "Passenger GPS requires a valid passenger login")
        if user.role != models.UserRole.PASSENGER:
            raise HTTPException(403, "Only passengers may submit passenger GPS")
        if not payload.ticket_id:
            raise HTTPException(400, "Passenger GPS requires ticket_id")
        ticket = db.query(models.Ticket).filter(models.Ticket.id == payload.ticket_id).first()
        if not ticket or ticket.passenger_id != user.id:
            raise HTTPException(403, "Invalid ticket for passenger GPS")
        if not ticket.boarded or ticket.trip_id != trip.id:
            raise HTTPException(400, "GPS can only be reported after boarding this trip")
    elif payload.source == "bus_device":
        user = _decode_optional_user(authorization, db)
        if not user or user.role not in (models.UserRole.DRIVER, models.UserRole.CONDUCTOR, models.UserRole.ADMIN):
            raise HTTPException(401, "bus_device pings require a DRIVER/CONDUCTOR/ADMIN token")
        if user.role in (models.UserRole.DRIVER, models.UserRole.CONDUCTOR) and user.assigned_bus_id != trip.bus_id:
            raise HTTPException(403, "You are not assigned to this bus")
    else:
        raise HTTPException(400, "source must be 'bus_device' or 'passenger'")

    ping = models.GPSPing(
        trip_id=trip.id,
        source=payload.source,
        ticket_id=payload.ticket_id,
        lat=payload.lat,
        lng=payload.lng,
        reported_at=datetime.utcnow(),
    )
    db.add(ping)
    db.flush()

    estimate = gps_aggregation_service.estimate_position(db, trip.id)
    if estimate:
        trip.current_lat = estimate["lat"]
        trip.current_lng = estimate["lng"]
        trip.last_location_update = estimate["reported_at"]
    db.commit()

    return {"message": "Location recorded", "trip_id": trip.id, "current_estimate": estimate}


@router.get("/trip/{trip_id}/live", response_model=schemas.TripLiveOut)
def get_live_status(trip_id: str, db: Session = Depends(get_db)):
    trip = db.query(models.Trip).filter(models.Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(404, "Trip not found")

    crowd = crowd_service.get_crowd_status(db, trip_id)
    position = gps_aggregation_service.estimate_position(db, trip_id)
    if position:
        current_lat = position["lat"]
        current_lng = position["lng"]
        last_update = position["reported_at"]
    else:
        current_lat = current_lng = None
        last_update = None

    return schemas.TripLiveOut(
        trip_id=trip.id,
        status=trip.status,
        delay_minutes=trip.delay_minutes,
        current_lat=current_lat,
        current_lng=current_lng,
        last_location_update=last_update,
        crowd_level=crowd["overall_level"] if crowd else None,
        location_confidence=position["confidence"] if position else None,
        location_source=position["method"] if position else None,
    )


@router.get("/trip/{trip_id}/eta")
def get_eta(trip_id: str, dest_lat: float, dest_lng: float, db: Session = Depends(get_db)):
    trip = db.query(models.Trip).filter(models.Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(404, "Trip not found")
    position = gps_aggregation_service.estimate_position(db, trip_id)
    if not position:
        raise HTTPException(404, "No recent live location available for this trip")

    return eta_service.get_eta(
        origin_lat=position["lat"], origin_lng=position["lng"],
        dest_lat=dest_lat, dest_lng=dest_lng,
    )
