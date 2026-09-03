from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import models
from app.schemas import schemas

router = APIRouter(prefix="/routes", tags=["Routes & Fares"])


@router.get("/", response_model=list[schemas.RouteOut])
def list_routes(db: Session = Depends(get_db)):
    return db.query(models.Route).all()


@router.get("/{route_id}", response_model=schemas.RouteOut)
def get_route(route_id: str, db: Session = Depends(get_db)):
    route = db.query(models.Route).filter(models.Route.id == route_id).first()
    if not route:
        raise HTTPException(404, "Route not found")
    return route


@router.get("/search/by-cities")
def search_routes(origin: str, destination: str, db: Session = Depends(get_db)):
    """Find routes matching an origin/destination city pair (case-insensitive)."""
    routes = db.query(models.Route).filter(
        models.Route.origin.ilike(f"%{origin}%"),
        models.Route.destination.ilike(f"%{destination}%"),
    ).all()
    if not routes:
        raise HTTPException(404, "No routes found for this origin/destination")
    return routes


@router.get("/{route_id}/fare")
def get_fare(route_id: str, from_stop: str, to_stop: str, db: Session = Depends(get_db)):
    """Fare between any two stops on a route = difference of their fare_from_origin."""
    stops = db.query(models.Stop).filter(models.Stop.route_id == route_id).all()
    stop_map = {s.name.lower(): s for s in stops}

    from_s = stop_map.get(from_stop.lower())
    to_s = stop_map.get(to_stop.lower())
    if not from_s or not to_s:
        raise HTTPException(404, "Stop not found on this route")
    if from_s.id == to_s.id:
        raise HTTPException(400, "Origin and destination cannot be the same stop")
    if from_s.sequence >= to_s.sequence:
        route = db.query(models.Route).filter(models.Route.id == route_id).first()
        raise HTTPException(
            400,
            f"This route only runs {route.origin} \u2192 {route.destination}. "
            f"'{from_s.name}' comes after or at '{to_s.name}' on this route, "
            f"so this direction isn't served here.",
        )

    fare = round(to_s.fare_from_origin - from_s.fare_from_origin, 2)
    return {
        "route_id": route_id,
        "from_stop": from_s.name,
        "to_stop": to_s.name,
        "fare": fare,
    }
