"""
Digitally reproduces the physical bus-stand departure board:

  BAY   DESTINATION      DEPARTURE   STATUS
  01    DELHI            08:30 AM    ON TIME
  02    AMBALA           08:45 AM    ON TIME
  ...

Deliberately shows ONE destination per row — never a "via" list — matching
what a passenger standing at the stand actually sees. Tapping a row goes to
/terminals/trips/{trip_id}/board for the full stop-by-stop route, fare, and
bus details.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import models
from app.schemas import schemas
from app.routers.buses import _validate_trip_date, _get_or_create_trip

router = APIRouter(prefix="/terminals", tags=["Departure Board"])


@router.get("/", response_model=list[schemas.TerminalOut])
def list_terminals(db: Session = Depends(get_db)):
    return db.query(models.Terminal).all()


@router.get("/{terminal_id}/departures", response_model=list[schemas.DepartureBoardEntry])
def departure_board(terminal_id: str, trip_date: str, db: Session = Depends(get_db)):
    """
    The board itself: every route departing from this terminal today,
    one row per bus, sorted by departure time — exactly like the physical
    sign, not a route-database view.
    """
    trip_date = _validate_trip_date(trip_date)
    terminal = db.query(models.Terminal).filter(models.Terminal.id == terminal_id).first()
    if not terminal:
        raise HTTPException(404, "Terminal not found")

    routes = db.query(models.Route).filter(models.Route.origin_terminal_id == terminal_id).all()
    if not routes:
        raise HTTPException(404, "No routes depart from this terminal")

    entries = []
    for route in routes:
        full_fare = max((s.fare_from_origin for s in route.stops), default=0.0)
        buses = db.query(models.Bus).filter(models.Bus.route_id == route.id).all()
        for bus in buses:
            trip = _get_or_create_trip(db, bus.id, trip_date)
            entries.append(schemas.DepartureBoardEntry(
                bay=bus.bay_number,
                destination=route.board_destination or route.destination,
                departure_time=bus.departure_time,
                status=trip.status,
                delay_minutes=trip.delay_minutes,
                trip_id=trip.id,
                route_id=route.id,
                bus_vehicle_number=bus.vehicle_number,
                fare=full_fare,
            ))
    db.commit()

    entries.sort(key=lambda e: e.departure_time)
    return entries


@router.get("/trips/{trip_id}/board", response_model=schemas.TripBoardDetail)
def trip_board_detail(trip_id: str, db: Session = Depends(get_db)):
    """
    The tap-through screen for a single departure-board row: fare, bus,
    operator, and the FULL stop-by-stop route (this is where "via" info
    belongs — under the destination, not on the board itself).
    """
    trip = db.query(models.Trip).filter(models.Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(404, "Trip not found")

    bus = trip.bus
    route = bus.route
    full_fare = max((s.fare_from_origin for s in route.stops), default=0.0)

    return schemas.TripBoardDetail(
        trip_id=trip.id,
        bay=bus.bay_number,
        board_destination=route.board_destination or route.destination,
        departure_time=bus.departure_time,
        status=trip.status,
        delay_minutes=trip.delay_minutes,
        fare=full_fare,
        bus_vehicle_number=bus.vehicle_number,
        operator_name=bus.operator_name,
        route=route,
    )
