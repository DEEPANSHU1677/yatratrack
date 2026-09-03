from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.models import CrowdLevel, TripStatus, UserRole


class UserRegister(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    phone: str = Field(min_length=3, max_length=30)
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.PASSENGER
    assigned_bus_id: Optional[str] = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    phone: str
    role: UserRole
    assigned_bus_id: Optional[str] = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: UserRole


class StopOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    sequence: int
    lat: Optional[float] = None
    lng: Optional[float] = None
    fare_from_origin: float


class RouteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    origin: str
    destination: str
    stops: List[StopOut] = Field(default_factory=list)


class BusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    vehicle_number: str
    qr_code: str
    operator_name: Optional[str] = None
    departure_time: str


class TripSearchResult(BaseModel):
    trip_id: str
    bus_vehicle_number: str
    operator_name: Optional[str]
    departure_time: str
    fare: float
    status: TripStatus
    delay_minutes: int
    crowd_level: Optional[str] = None


# ---------- Terminal / Departure Board ----------
# Deliberately mirrors what a physical bus-stand board shows: bay, single
# destination name, time, status — NOT the intermediate "via" stop list.
# The full route is only shown after the passenger taps a row (see
# TripBoardDetail below).

class TerminalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    city: str
    lat: Optional[float] = None
    lng: Optional[float] = None


class DepartureBoardEntry(BaseModel):
    bay: Optional[str] = None
    destination: str  # board_destination if set, else route.destination
    departure_time: str
    status: TripStatus
    delay_minutes: int
    trip_id: str
    route_id: str
    bus_vehicle_number: str
    fare: float


class TripBoardDetail(BaseModel):
    """The tap-through screen: fare, bus, and the full stop-by-stop route."""
    trip_id: str
    bay: Optional[str] = None
    board_destination: str
    departure_time: str
    status: TripStatus
    delay_minutes: int
    fare: float
    bus_vehicle_number: str
    operator_name: Optional[str] = None
    route: RouteOut


class TicketCreate(BaseModel):
    route_id: str
    passenger_name: str = Field(min_length=1, max_length=100)
    origin_stop: str = Field(min_length=1, max_length=100)
    destination_stop: str = Field(min_length=1, max_length=100)


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    route_id: str
    passenger_name: str
    origin_stop: str
    destination_stop: str
    fare: float
    boarded: bool
    trip_id: Optional[str] = None


class BoardBusRequest(BaseModel):
    ticket_id: str
    qr_code: Optional[str] = None
    vehicle_number: Optional[str] = None
    trip_date: str


class GPSPingCreate(BaseModel):
    trip_id: str
    source: str
    ticket_id: Optional[str] = None
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class CrowdReportCreate(BaseModel):
    trip_id: str
    ticket_id: Optional[str] = None
    level: CrowdLevel


class CrowdStatusOut(BaseModel):
    trip_id: str
    overall_level: str
    report_count: int
    breakdown: dict


class TripStatusUpdate(BaseModel):
    status: TripStatus
    delay_minutes: int = Field(default=0, ge=0, le=1440)


class TripLiveOut(BaseModel):
    trip_id: str
    status: TripStatus
    delay_minutes: int
    current_lat: Optional[float]
    current_lng: Optional[float]
    last_location_update: Optional[datetime]
    crowd_level: Optional[str] = None
    location_confidence: Optional[str] = None
    location_source: Optional[str] = None
