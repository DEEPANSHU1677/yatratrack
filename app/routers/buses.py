from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import require_roles
from app.database import get_db
from app.models import models
from app.schemas import schemas
from app.services import crowd_service, gps_aggregation_service

router = APIRouter(prefix="/buses", tags=["Bus Search"])


def _validate_trip_date(trip_date: str) -> str:
    try:
        return datetime.strptime(trip_date, "%Y-%m-%d").date().isoformat()
    except ValueError as exc:
        raise HTTPException(400, "trip_date must use YYYY-MM-DD format") from exc


def _get_or_create_trip(db: Session, bus_id: str, trip_date: str):
    trip = db.query(models.Trip).filter(
        models.Trip.bus_id == bus_id, models.Trip.trip_date == trip_date
    ).first()
    if trip:
        return trip
    trip = models.Trip(bus_id=bus_id, trip_date=trip_date)
    db.add(trip)
    db.flush()
    return trip


def _segment_fare(route, origin_name: str, destination_name: str) -> float:
    stops = {s.name.casefold(): s for s in route.stops}
    origin = stops.get(origin_name.casefold())
    destination = stops.get(destination_name.casefold())
    if not origin or not destination or origin.sequence >= destination.sequence:
        return 0.0
    return round(destination.fare_from_origin - origin.fare_from_origin, 2)


def _buses_for_route(db: Session, route, trip_date: str, origin_name: str | None = None, destination_name: str | None = None):
    buses = db.query(models.Bus).filter(models.Bus.route_id == route.id).order_by(models.Bus.departure_time).all()
    if not buses:
        return []

    fare = max((s.fare_from_origin for s in route.stops), default=0)
    if origin_name and destination_name:
        fare = _segment_fare(route, origin_name, destination_name)

    results = []
    for bus in buses:
        trip = _get_or_create_trip(db, bus.id, trip_date)
        crowd = crowd_service.get_crowd_status(db, trip.id)
        position = gps_aggregation_service.estimate_position(db, trip.id)
        results.append(schemas.TripSearchResult(
            trip_id=trip.id,
            bus_vehicle_number=bus.vehicle_number,
            operator_name=bus.operator_name,
            departure_time=bus.departure_time,
            fare=fare,
            status=trip.status,
            delay_minutes=trip.delay_minutes,
            crowd_level=crowd["overall_level"] if crowd else None,
        ))
    db.commit()
    return results


@router.get("/search", response_model=list[schemas.TripSearchResult])
def search_buses(route_id: str, trip_date: str | None = None, db: Session = Depends(get_db)):
    trip_date = _validate_trip_date(trip_date or str(date.today()))
    route = db.query(models.Route).filter(models.Route.id == route_id).first()
    if not route:
        raise HTTPException(404, "Route not found")
    results = _buses_for_route(db, route, trip_date)
    if not results:
        raise HTTPException(404, "No buses found for this route")
    return results


@router.get("/journey")
def search_journey(origin: str, destination: str, trip_date: str | None = None, db: Session = Depends(get_db)):
    """Find routes where origin/destination are ordered stops, not just route endpoints."""
    origin = origin.strip()
    destination = destination.strip()
    if not origin or not destination:
        raise HTTPException(400, "origin and destination are required")
    trip_date = _validate_trip_date(trip_date or str(date.today()))

    matched = []
    for route in db.query(models.Route).all():
        stops = {s.name.casefold(): s for s in route.stops}
        from_s = stops.get(origin.casefold())
        to_s = stops.get(destination.casefold())
        if from_s and to_s and from_s.sequence < to_s.sequence:
            matched.append((route, from_s.name, to_s.name))

    if not matched:
        raise HTTPException(404, "No route serves this journey in the requested direction")

    response = []
    for route, from_name, to_name in matched:
        buses = _buses_for_route(db, route, trip_date, from_name, to_name)
        from_seq = next(s.sequence for s in route.stops if s.name.casefold() == from_name.casefold())
        to_seq = next(s.sequence for s in route.stops if s.name.casefold() == to_name.casefold())
        response.append({
            "route_id": route.id,
            "route_name": route.name,
            "origin": from_name,
            "destination": to_name,
            "buses": buses,
            "stops": [
                {"name": s.name, "sequence": s.sequence, "lat": s.lat, "lng": s.lng}
                for s in route.stops if from_seq <= s.sequence <= to_seq
            ],
        })
    db.commit()
    return response


@router.patch("/trips/{trip_id}/status")
def update_trip_status(
    trip_id: str,
    update: schemas.TripStatusUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles("CONDUCTOR", "OPERATOR", "ADMIN")),
):
    trip = db.query(models.Trip).filter(models.Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(404, "Trip not found")

    if current_user.role in (models.UserRole.CONDUCTOR,) and current_user.assigned_bus_id != trip.bus_id:
        raise HTTPException(403, "You are not assigned to this bus")

    delay = update.delay_minutes
    if update.status == models.TripStatus.CANCELLED:
        delay = 0
    elif update.status == models.TripStatus.ON_TIME:
        delay = 0
    elif delay == 0:
        raise HTTPException(400, "A DELAYED trip must have delay_minutes greater than 0")

    trip.status = update.status
    trip.delay_minutes = delay
    db.commit()
    return {"trip_id": trip.id, "status": trip.status, "delay_minutes": trip.delay_minutes}
