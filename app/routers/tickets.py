from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_roles
from app.database import get_db
from app.models import models
from app.schemas import schemas

router = APIRouter(prefix="/tickets", tags=["Tickets & Boarding"])


def _ordered_stops(db: Session, route_id: str):
    route = db.query(models.Route).filter(models.Route.id == route_id).first()
    if not route:
        raise HTTPException(404, "Route not found")
    return route, sorted(route.stops, key=lambda s: s.sequence)


def _find_stop(stops, name: str):
    target = name.strip().casefold()
    return next((s for s in stops if s.name.casefold() == target), None)


def _validate_trip_date(trip_date: str) -> str:
    try:
        return datetime.strptime(trip_date, "%Y-%m-%d").date().isoformat()
    except ValueError as exc:
        raise HTTPException(400, "trip_date must use YYYY-MM-DD format") from exc


@router.post("/", response_model=schemas.TicketOut)
def create_ticket(
    payload: schemas.TicketCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles("PASSENGER")),
):
    route, stops = _ordered_stops(db, payload.route_id)
    from_s = _find_stop(stops, payload.origin_stop)
    to_s = _find_stop(stops, payload.destination_stop)
    if not from_s or not to_s:
        raise HTTPException(404, "Origin or destination stop not found on this route")
    if from_s.sequence >= to_s.sequence:
        raise HTTPException(400, f"This route only runs {route.origin} → {route.destination} in the selected direction")

    fare = round(to_s.fare_from_origin - from_s.fare_from_origin, 2)
    ticket = models.Ticket(
        route_id=payload.route_id,
        passenger_id=current_user.id,
        passenger_name=current_user.name,
        origin_stop=from_s.name,
        destination_stop=to_s.name,
        fare=fare,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


@router.get("/{ticket_id}", response_model=schemas.TicketOut)
def get_ticket(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    ticket = db.query(models.Ticket).filter(models.Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    if ticket.passenger_id is None and current_user.role == models.UserRole.PASSENGER:
        raise HTTPException(403, "Ticket is not linked to a passenger account")
    if ticket.passenger_id not in (None, current_user.id) and current_user.role not in (
        models.UserRole.CONDUCTOR, models.UserRole.OPERATOR, models.UserRole.ADMIN
    ):
        raise HTTPException(403, "You do not have access to this ticket")
    return ticket


@router.post("/board")
def board_bus(
    payload: schemas.BoardBusRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    ticket = db.query(models.Ticket).filter(models.Ticket.id == payload.ticket_id).first()
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    if ticket.passenger_id is None and current_user.role == models.UserRole.PASSENGER:
        raise HTTPException(403, "Ticket is not linked to a passenger account")
    if ticket.passenger_id not in (None, current_user.id) and current_user.role not in (
        models.UserRole.CONDUCTOR, models.UserRole.OPERATOR, models.UserRole.ADMIN
    ):
        raise HTTPException(403, "You do not own this ticket")
    if ticket.boarded:
        raise HTTPException(409, "Ticket has already been boarded")
    if bool(payload.qr_code) == bool(payload.vehicle_number):
        raise HTTPException(400, "Provide exactly one of qr_code or vehicle_number")

    bus = None
    if payload.qr_code:
        bus = db.query(models.Bus).filter(models.Bus.qr_code == payload.qr_code.strip()).first()
    else:
        bus = db.query(models.Bus).filter(models.Bus.vehicle_number == payload.vehicle_number.strip().upper()).first()
    if not bus:
        raise HTTPException(404, "Bus not recognized (check QR code / vehicle number)")
    if bus.route_id != ticket.route_id:
        raise HTTPException(400, "Selected bus does not operate on this ticket's route")

    trip_date = _validate_trip_date(payload.trip_date)
    trip = db.query(models.Trip).filter(
        models.Trip.bus_id == bus.id, models.Trip.trip_date == trip_date
    ).first()
    if not trip:
        trip = models.Trip(bus_id=bus.id, trip_date=trip_date)
        db.add(trip)
        db.flush()

    if trip.status == models.TripStatus.CANCELLED:
        raise HTTPException(409, "This bus trip is cancelled")

    ticket.trip_id = trip.id
    ticket.boarded = True
    db.commit()

    return {
        "message": "Boarding confirmed",
        "ticket_id": ticket.id,
        "trip_id": trip.id,
        "bus_vehicle_number": bus.vehicle_number,
        "operator": bus.operator_name,
    }
