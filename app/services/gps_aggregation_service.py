import math
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models import models

RECENT_WINDOW_SECONDS = 180
AGREEMENT_RADIUS_KM = 0.3
OUTLIER_RADIUS_KM = 1.0


def _haversine_km(lat1, lng1, lat2, lng2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _median_point(points):
    lats = sorted(p[0] for p in points)
    lngs = sorted(p[1] for p in points)
    return lats[len(points) // 2], lngs[len(points) // 2]


def estimate_position(db: Session, trip_id: str):
    cutoff = datetime.utcnow() - timedelta(seconds=RECENT_WINDOW_SECONDS)
    recent = db.query(models.GPSPing).filter(
        models.GPSPing.trip_id == trip_id,
        models.GPSPing.reported_at >= cutoff,
    ).order_by(models.GPSPing.reported_at.desc()).all()
    if not recent:
        return None

    bus_pings = [p for p in recent if p.source == "bus_device"]
    if bus_pings:
        latest = bus_pings[0]
        return {
            "lat": latest.lat, "lng": latest.lng,
            "confidence": "HIGH", "method": "official_bus_gps",
            "contributing_reports": 1, "reported_at": latest.reported_at,
        }

    passenger_pings = [p for p in recent if p.source == "passenger"]
    if not passenger_pings:
        return None

    points = [(p.lat, p.lng) for p in passenger_pings]
    median = _median_point(points)
    inliers = [pt for pt in points if _haversine_km(*median, *pt) <= OUTLIER_RADIUS_KM]
    if not inliers:
        return None

    clusters = []
    for pt in inliers:
        placed = False
        for cluster in clusters:
            centroid = (
                sum(p[0] for p in cluster) / len(cluster),
                sum(p[1] for p in cluster) / len(cluster),
            )
            if _haversine_km(*centroid, *pt) <= AGREEMENT_RADIUS_KM:
                cluster.append(pt)
                placed = True
                break
        if not placed:
            clusters.append([pt])

    best_cluster = max(clusters, key=len)
    if len(best_cluster) == 1 and len(passenger_pings) > 1:
        confidence = "LOW"
    elif len(best_cluster) >= 3:
        confidence = "HIGH"
    elif len(best_cluster) == 2:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    # Use the newest contributing ping so the displayed timestamp is honest.
    cluster_set = set(best_cluster)
    contributing = [p for p in passenger_pings if (p.lat, p.lng) in cluster_set]
    latest = max(contributing, key=lambda p: p.reported_at)
    return {
        "lat": round(sum(p[0] for p in best_cluster) / len(best_cluster), 6),
        "lng": round(sum(p[1] for p in best_cluster) / len(best_cluster), 6),
        "confidence": confidence,
        "method": "crowdsourced_passenger_gps",
        "contributing_reports": len(best_cluster),
        "reported_at": latest.reported_at,
    }
