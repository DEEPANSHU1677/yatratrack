"""Reset and populate deterministic demo data for the hackathon.

Run:
    python seed_data.py

Demo logins:
    passenger: 9999999999 / passenger123
    driver:    9999999998 / driver123
    conductor: 9999999997 / conductor123
"""
from app.auth import hash_password
from app.database import SessionLocal, Base, engine
from app.models import models

Base.metadata.create_all(bind=engine)
db = SessionLocal()
try:
    # Users must be removed before buses they may reference.
    for model in [models.GPSPing, models.CrowdReport, models.Ticket,
                  models.Trip, models.User, models.Bus, models.Stop,
                  models.Route, models.Terminal]:
        db.query(model).delete(synchronize_session=False)
    db.commit()

    # ---------------------------------------------------------------
    # 1. Jalandhar - Pathankot (kept for continuity with earlier tests)
    # ---------------------------------------------------------------
    route = models.Route(
        name="Jalandhar - Pathankot",
        origin="Jalandhar",
        destination="Pathankot",
    )
    db.add(route)
    db.flush()

    stops_data = [
        ("Jalandhar", 0, 31.3260, 75.5762, 0),
        ("Kartarpur", 1, 31.4440, 75.4980, 20),
        ("Beas", 2, 31.5190, 75.2860, 40),
        ("Mukerian", 3, 31.9530, 75.6180, 90),
        ("Pathankot", 4, 32.2740, 75.6520, 120),
    ]
    for name, seq, lat, lng, fare in stops_data:
        db.add(models.Stop(
            route_id=route.id, name=name, sequence=seq,
            lat=lat, lng=lng, fare_from_origin=fare,
        ))

    db.flush()
    buses_data = [
        ("PB07AA1234", "QR-YATRA-A1", "Punjab Roadways", "08:30"),
        ("PB08BB5678", "QR-YATRA-B2", "Demo Private Travels", "08:45"),
        ("PB10CC9012", "QR-YATRA-C3", "Punjab Roadways", "09:15"),
    ]
    buses = []
    for vehicle_number, qr, operator, dep_time in buses_data:
        bus = models.Bus(
            route_id=route.id,
            vehicle_number=vehicle_number,
            qr_code=qr,
            operator_name=operator,
            departure_time=dep_time,
        )
        buses.append(bus)
        db.add(bus)

    db.flush()

    demo_users = [
        models.User(name="Demo Passenger", phone="9999999999", hashed_password=hash_password("passenger123"), role=models.UserRole.PASSENGER),
        models.User(name="Demo Driver", phone="9999999998", hashed_password=hash_password("driver123"), role=models.UserRole.DRIVER, assigned_bus_id=buses[0].id),
        models.User(name="Demo Conductor", phone="9999999997", hashed_password=hash_password("conductor123"), role=models.UserRole.CONDUCTOR, assigned_bus_id=buses[0].id),
    ]
    db.add_all(demo_users)
    db.flush()

    # ---------------------------------------------------------------
    # 2. Ludhiana Bus Stand — departure board demo
    #    One Route per board destination (no "via" list on the board
    #    itself — see /terminals/{id}/departures).
    # ---------------------------------------------------------------
    ludhiana_terminal = models.Terminal(
        name="Ludhiana Bus Stand", city="Ludhiana", lat=30.9010, lng=75.8573,
    )
    jalandhar_terminal = models.Terminal(
        name="Jalandhar Bus Stand", city="Jalandhar", lat=31.3260, lng=75.5762,
    )
    db.add_all([ludhiana_terminal, jalandhar_terminal])
    db.flush()

    # Simple single-hop board destinations (no detailed intermediate stops
    # needed for the demo — board just needs a valid route + one bus each).
    simple_board_routes = [
        # (destination, bay, departure_time, distance_fare)
        ("Delhi", "01", "08:30", 450),
        ("Ambala", "02", "08:45", 180),
        ("Chandigarh", "03", "09:00", 120),
        ("Mohali", "04", "09:20", 130),
        ("Amritsar", "06", "10:00", 140),
    ]
    for i, (dest, bay, dep_time, fare) in enumerate(simple_board_routes):
        r = models.Route(
            name=f"Ludhiana - {dest}",
            origin="Ludhiana",
            destination=dest,
            origin_terminal_id=ludhiana_terminal.id,
        )
        db.add(r)
        db.flush()
        db.add(models.Stop(route_id=r.id, name="Ludhiana", sequence=0, lat=30.9010, lng=75.8573, fare_from_origin=0))
        db.add(models.Stop(route_id=r.id, name=dest, sequence=1, fare_from_origin=fare))
        db.flush()
        db.add(models.Bus(
            route_id=r.id,
            vehicle_number=f"PB13X{1000 + i}",
            qr_code=f"QR-LDH-{dest.upper()}",
            operator_name="Punjab Roadways",
            departure_time=dep_time,
            bay_number=bay,
        ))

    # Ludhiana -> Jalandhar: the detailed example route with real
    # intermediate stops (Bay 05 on the board; full route only shown on tap).
    ludhiana_jalandhar = models.Route(
        name="Ludhiana - Jalandhar",
        origin="Ludhiana",
        destination="Jalandhar",
        board_destination="Jalandhar",
        origin_terminal_id=ludhiana_terminal.id,
    )
    db.add(ludhiana_jalandhar)
    db.flush()

    lj_stops = [
        ("Ludhiana", 0, 30.9010, 75.8573, 0),
        ("Samrala Chowk", 1, 30.8340, 76.1900, 20),
        ("Phillaur", 2, 31.0169, 75.7911, 45),
        ("Goraya", 3, 31.1421, 75.7891, 65),
        ("Phagwara", 4, 31.2240, 75.7708, 85),
        ("Rama Mandi", 5, 31.2900, 75.6100, 95),
        ("Jalandhar", 6, 31.3260, 75.5762, 100),
    ]
    for name, seq, lat, lng, fare in lj_stops:
        db.add(models.Stop(route_id=ludhiana_jalandhar.id, name=name, sequence=seq, lat=lat, lng=lng, fare_from_origin=fare))
    db.flush()
    db.add(models.Bus(
        route_id=ludhiana_jalandhar.id,
        vehicle_number="PB08AB1234",
        qr_code="QR-LDH-JALANDHAR",
        operator_name="Punjab Roadways",
        departure_time="09:30",
        bay_number="05",
    ))

    # Reverse direction (Option A: a separate Route, not the same one
    # walked backwards) — departs from the Jalandhar terminal instead.
    jalandhar_ludhiana = models.Route(
        name="Jalandhar - Ludhiana",
        origin="Jalandhar",
        destination="Ludhiana",
        board_destination="Ludhiana",
        origin_terminal_id=jalandhar_terminal.id,
    )
    db.add(jalandhar_ludhiana)
    db.flush()
    reversed_stops = [
        (name, (len(lj_stops) - 1) - seq, lat, lng, lj_stops[-1][4] - fare)
        for name, seq, lat, lng, fare in lj_stops
    ]
    for name, seq, lat, lng, fare in reversed_stops:
        db.add(models.Stop(route_id=jalandhar_ludhiana.id, name=name, sequence=seq, lat=lat, lng=lng, fare_from_origin=fare))
    db.flush()
    db.add(models.Bus(
        route_id=jalandhar_ludhiana.id,
        vehicle_number="PB08AB5678",
        qr_code="QR-JAL-LUDHIANA",
        operator_name="Punjab Roadways",
        departure_time="17:30",
        bay_number="02",
    ))

    db.commit()

    print("Seed complete.")
    print(f"Jalandhar-Pathankot route ID: {route.id}")
    print("Demo users:")
    print("  Passenger 9999999999 / passenger123")
    print("  Driver    9999999998 / driver123")
    print("  Conductor 9999999997 / conductor123")
    for bus in buses:
        print(f"  Bus {bus.vehicle_number} | QR: {bus.qr_code} | id: {bus.id}")
    print(f"Ludhiana Bus Stand terminal ID: {ludhiana_terminal.id}")
    print(f"Jalandhar Bus Stand terminal ID: {jalandhar_terminal.id}")
finally:
    db.close()
