import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


def gen_id():
    return str(uuid.uuid4())


class CrowdLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class TripStatus(str, enum.Enum):
    ON_TIME = "ON_TIME"
    DELAYED = "DELAYED"
    CANCELLED = "CANCELLED"


class UserRole(str, enum.Enum):
    PASSENGER = "PASSENGER"
    DRIVER = "DRIVER"
    CONDUCTOR = "CONDUCTOR"
    OPERATOR = "OPERATOR"
    ADMIN = "ADMIN"


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, nullable=False)
    phone = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.PASSENGER, nullable=False)
    assigned_bus_id = Column(String, ForeignKey("buses.id"), nullable=True)


class Terminal(Base):
    """A physical bus stand/terminal — e.g. 'Ludhiana Bus Stand'."""
    __tablename__ = "terminals"
    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, nullable=False)  # "Ludhiana Bus Stand"
    city = Column(String, nullable=False, index=True)  # "Ludhiana"
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)

    departing_routes = relationship(
        "Route", foreign_keys="Route.origin_terminal_id", back_populates="origin_terminal"
    )


class Route(Base):
    __tablename__ = "routes"
    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, nullable=False)
    origin = Column(String, nullable=False)
    destination = Column(String, nullable=False)

    # What the physical departure board actually prints for this route's
    # destination column — usually equal to `destination`, but kept separate
    # so it can be overridden without touching the canonical stop network
    # (e.g. board says "DELHI", route's final stop is officially "Delhi ISBT").
    board_destination = Column(String, nullable=True)

    # Origin terminal this route departs from, for the departure-board view.
    # Nullable so existing routes without a terminal still work.
    origin_terminal_id = Column(String, ForeignKey("terminals.id"), nullable=True, index=True)

    stops = relationship(
        "Stop", back_populates="route", order_by="Stop.sequence", cascade="all, delete-orphan"
    )
    buses = relationship("Bus", back_populates="route")
    origin_terminal = relationship("Terminal", foreign_keys=[origin_terminal_id], back_populates="departing_routes")


class Stop(Base):
    __tablename__ = "stops"
    __table_args__ = (UniqueConstraint("route_id", "sequence", name="uq_stop_route_sequence"),)

    id = Column(String, primary_key=True, default=gen_id)
    route_id = Column(String, ForeignKey("routes.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    sequence = Column(Integer, nullable=False)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    fare_from_origin = Column(Float, nullable=False)

    route = relationship("Route", back_populates="stops")


class Bus(Base):
    __tablename__ = "buses"
    id = Column(String, primary_key=True, default=gen_id)
    vehicle_number = Column(String, unique=True, nullable=False, index=True)
    qr_code = Column(String, unique=True, nullable=False, index=True)
    operator_name = Column(String, nullable=True)
    route_id = Column(String, ForeignKey("routes.id"), nullable=False, index=True)
    departure_time = Column(String, nullable=False)
    bay_number = Column(String, nullable=True)  # e.g. "05" — printed on the departure board

    route = relationship("Route", back_populates="buses")
    trips = relationship("Trip", back_populates="bus", cascade="all, delete-orphan")


class Trip(Base):
    __tablename__ = "trips"
    __table_args__ = (UniqueConstraint("bus_id", "trip_date", name="uq_trip_bus_date"),)

    id = Column(String, primary_key=True, default=gen_id)
    bus_id = Column(String, ForeignKey("buses.id"), nullable=False, index=True)
    trip_date = Column(String, nullable=False, index=True)
    status = Column(Enum(TripStatus), default=TripStatus.ON_TIME, nullable=False)
    delay_minutes = Column(Integer, default=0, nullable=False)
    current_lat = Column(Float, nullable=True)
    current_lng = Column(Float, nullable=True)
    last_location_update = Column(DateTime, nullable=True)

    bus = relationship("Bus", back_populates="trips")
    tickets = relationship("Ticket", back_populates="trip")
    gps_pings = relationship("GPSPing", back_populates="trip", cascade="all, delete-orphan")
    crowd_reports = relationship("CrowdReport", back_populates="trip", cascade="all, delete-orphan")


class Ticket(Base):
    __tablename__ = "tickets"
    id = Column(String, primary_key=True, default=gen_id)
    trip_id = Column(String, ForeignKey("trips.id"), nullable=True, index=True)
    route_id = Column(String, ForeignKey("routes.id"), nullable=False, index=True)
    passenger_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    passenger_name = Column(String, nullable=False)
    origin_stop = Column(String, nullable=False)
    destination_stop = Column(String, nullable=False)
    fare = Column(Float, nullable=False)
    boarded = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    trip = relationship("Trip", back_populates="tickets")
    passenger = relationship("User")


class GPSPing(Base):
    __tablename__ = "gps_pings"
    id = Column(String, primary_key=True, default=gen_id)
    trip_id = Column(String, ForeignKey("trips.id"), nullable=False, index=True)
    source = Column(String, nullable=False)
    ticket_id = Column(String, ForeignKey("tickets.id"), nullable=True, index=True)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    reported_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    trip = relationship("Trip", back_populates="gps_pings")
    ticket = relationship("Ticket")


class CrowdReport(Base):
    __tablename__ = "crowd_reports"
    id = Column(String, primary_key=True, default=gen_id)
    trip_id = Column(String, ForeignKey("trips.id"), nullable=False, index=True)
    ticket_id = Column(String, ForeignKey("tickets.id"), nullable=True, index=True)
    level = Column(Enum(CrowdLevel), nullable=False)
    reported_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    trip = relationship("Trip", back_populates="crowd_reports")
    ticket = relationship("Ticket")
