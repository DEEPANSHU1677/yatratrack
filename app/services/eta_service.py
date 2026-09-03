import json
import math
import os
from urllib import error, request

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")


def _haversine_km(lat1, lng1, lat2, lng2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return R * (2 * math.asin(math.sqrt(a)))


def _parse_duration_seconds(duration: str) -> int:
    if not duration.endswith("s"):
        raise ValueError("Unexpected Google duration format")
    return round(float(duration[:-1]))


def _google_eta(origin_lat, origin_lng, dest_lat, dest_lng):
    body = {
        "origin": {"location": {"latLng": {"latitude": origin_lat, "longitude": origin_lng}}},
        "destination": {"location": {"latLng": {"latitude": dest_lat, "longitude": dest_lng}}},
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
        "languageCode": "en-US",
        "units": "METRIC",
    }
    req = request.Request(
        "https://routes.googleapis.com/directions/v2:computeRoutes",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": GOOGLE_MAPS_API_KEY,
            "X-Goog-FieldMask": "routes.duration,routes.staticDuration,routes.distanceMeters",
        },
        method="POST",
    )
    with request.urlopen(req, timeout=5) as response:
        data = json.loads(response.read().decode("utf-8"))
    routes = data.get("routes") or []
    if not routes:
        raise ValueError("Google Routes API returned no route")
    route = routes[0]
    traffic_seconds = _parse_duration_seconds(route["duration"])
    static_seconds = _parse_duration_seconds(route.get("staticDuration", route["duration"]))
    return {
        "distance_km": round(route["distanceMeters"] / 1000, 2),
        "eta_minutes": max(1, round(traffic_seconds / 60)),
        "static_eta_minutes": max(1, round(static_seconds / 60)),
        "source": "google_routes_api",
        "traffic_aware": True,
    }


def get_eta(origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float):
    if GOOGLE_MAPS_API_KEY:
        try:
            return _google_eta(origin_lat, origin_lng, dest_lat, dest_lng)
        except (OSError, ValueError, KeyError, json.JSONDecodeError, error.URLError):
            pass

    distance_km = _haversine_km(origin_lat, origin_lng, dest_lat, dest_lng)
    assumed_speed_kmph = 30
    eta_minutes = max(1, round((distance_km / assumed_speed_kmph) * 60))
    return {
        "distance_km": round(distance_km, 2),
        "eta_minutes": eta_minutes,
        "source": "fallback_straight_line_estimate",
        "traffic_aware": False,
    }
