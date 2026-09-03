import math
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models import models

RECENT_CROWD_WINDOW_MINUTES = 15
LEVEL_WEIGHT = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
WEIGHT_LEVEL = {1: "LOW", 2: "MEDIUM", 3: "HIGH"}


def get_crowd_status(db: Session, trip_id: str):
    cutoff = datetime.utcnow() - timedelta(minutes=RECENT_CROWD_WINDOW_MINUTES)
    reports = db.query(models.CrowdReport).filter(
        models.CrowdReport.trip_id == trip_id,
        models.CrowdReport.reported_at >= cutoff,
    ).all()
    if not reports:
        return None

    breakdown = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
    total_weight = 0
    for r in reports:
        breakdown[r.level.value] += 1
        total_weight += LEVEL_WEIGHT[r.level.value]

    # Use round-half-up, not Python's built-in round() (round-half-to-even):
    # with round(), a MEDIUM+HIGH split (avg 2.5) rounds DOWN to MEDIUM -- the
    # same result as a LOW+MEDIUM split (avg 1.5, which rounds UP to MEDIUM) --
    # silently under-reporting a genuinely more crowded bus.
    avg_weight = min(max(math.floor(total_weight / len(reports) + 0.5), 1), 3)
    return {
        "trip_id": trip_id,
        "overall_level": WEIGHT_LEVEL[avg_weight],
        "report_count": len(reports),
        "breakdown": breakdown,
    }


def predict_crowd_at_stop(db: Session, trip_id: str, from_stop_sequence: int):
    trip = db.query(models.Trip).filter(models.Trip.id == trip_id).first()
    if not trip:
        return {"error": "Trip not found"}

    route_stops = sorted(trip.bus.route.stops, key=lambda s: s.sequence)
    valid_sequences = {s.sequence for s in route_stops}
    if from_stop_sequence not in valid_sequences:
        return {"error": "Stop sequence not found on this route"}

    tickets = db.query(models.Ticket).filter(
        models.Ticket.trip_id == trip_id,
        models.Ticket.boarded.is_(True),
    ).all()
    stop_seq_map = {s.name.casefold(): s.sequence for s in route_stops}

    total_boarded = len(tickets)
    expected_alighted = sum(
        1 for t in tickets
        if stop_seq_map.get(t.destination_stop.casefold()) is not None
        and stop_seq_map[t.destination_stop.casefold()] <= from_stop_sequence
    )
    remaining = max(total_boarded - expected_alighted, 0)

    if total_boarded == 0:
        predicted_level = "UNKNOWN"
    else:
        ratio = remaining / total_boarded
        predicted_level = "LOW" if ratio < 0.34 else "MEDIUM" if ratio < 0.67 else "HIGH"

    return {
        "trip_id": trip_id,
        "after_stop_sequence": from_stop_sequence,
        "total_boarded": total_boarded,
        "expected_remaining": remaining,
        "predicted_crowd_level": predicted_level,
        "note": "Estimate based on boarded ticket destinations; actual boarding/alighting may vary.",
    }
