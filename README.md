# YatraGPT Backend

FastAPI + SQLAlchemy backend for a smart public-bus travel platform: routes, stops, fares, schedules, digital tickets, bus identification, real-time GPS, ETA, status updates, and optional crowdsourced crowd information.

## What was fixed in this review

- Public registration can no longer create ADMIN/OPERATOR/DRIVER/CONDUCTOR accounts by default.
- Ticket creation is tied to the authenticated passenger; the submitted passenger name is not trusted.
- Passengers can only read/board their own tickets.
- A ticket can be boarded only once and only onto a bus serving the same route.
- Passenger GPS now requires an authenticated, boarded ticket belonging to that passenger.
- Official/bus-device GPS still requires DRIVER/CONDUCTOR/ADMIN authorization; drivers and conductors must be assigned to the bus.
- Passenger crowd reports require a valid ticket; one active report per ticket is updated instead of allowing vote spam.
- Crowd aggregation ignores reports older than 15 minutes.
- GPS aggregation ignores signals older than 3 minutes and returns the honest timestamp of the newest contributing signal.
- Stale live positions are no longer returned as if they were current.
- Trip dates are validated as `YYYY-MM-DD`.
- Latitude/longitude inputs are range-validated.
- Status updates enforce sensible delay values and prevent unassigned conductors from changing another bus's status.
- Journey search supports origin/destination **intermediate stops**, not only route endpoints.
- Fare is calculated from ordered stop sequences, preventing reverse-direction fares.
- Trip and stop uniqueness constraints reduce duplicate data.
- Google Routes API integration is now a real traffic-aware HTTP implementation when `GOOGLE_MAPS_API_KEY` is set; otherwise a clearly labelled fallback estimate is returned.
- CORS defaults to local frontend development origins and can be configured with `YATRAGPT_CORS_ORIGINS`.
- IDs use full UUIDs instead of truncating to 8 characters.

## Setup

```bash
pip install -r requirements.txt
python seed_data.py
uvicorn app.main:app --reload
```

Open `http://localhost:8000/docs` for Swagger UI.

### Demo accounts

`python seed_data.py` creates:

- Passenger: `9999999999 / passenger123`
- Driver: `9999999998 / driver123`
- Conductor: `9999999997 / conductor123`

For demo staff registration only, set:

```bash
YATRAGPT_ALLOW_DEMO_ROLE_REGISTRATION=1
```

Do not use that setting in production.

## Google traffic-aware ETA

Set:

```bash
GOOGLE_MAPS_API_KEY=your_key
```

The backend calls Google's Routes API `computeRoutes` endpoint with `TRAFFIC_AWARE`. The response uses the route duration that accounts for traffic. If the API is unavailable, the endpoint falls back to a straight-line estimate and explicitly reports `traffic_aware: false`.

## Security/configuration

For production set at minimum:

```bash
YATRAGPT_ENV=production
YATRAGPT_SECRET_KEY=<long-random-secret>
YATRAGPT_CORS_ORIGINS=https://your-frontend.example
```

SQLite is intentionally used for the hackathon demo. Production should move to PostgreSQL and preferably PostGIS for geospatial queries.

## API flow

1. `GET /buses/journey?origin=Jalandhar&destination=Pathankot` — passenger-facing search.
2. `GET /routes/{route_id}/fare?from_stop=...&to_stop=...` — applicable fare between ordered stops.
3. `POST /auth/register` + `POST /auth/login` — passenger authentication.
4. `POST /tickets/` — authenticated passenger buys a ticket.
5. `POST /tickets/board` — passenger scans a bus QR or enters the vehicle number.
6. `POST /gps/ping` — authenticated driver/conductor bus GPS or authenticated boarded passenger GPS.
7. `GET /gps/trip/{trip_id}/live` — live location, status, confidence and recent crowd level.
8. `GET /gps/trip/{trip_id}/eta?dest_lat=...&dest_lng=...` — traffic-aware ETA when Google is configured.
9. `POST /crowd/report` + `GET /crowd/trip/{trip_id}` — optional crowd reporting.
10. `PATCH /buses/trips/{trip_id}/status` — authorized delay/cancellation update.

## Departure board (Terminal → Board → Trip detail)

Mirrors what a passenger actually sees painted on the physical bus-stand board — one destination per row, no "via" list — rather than exposing the route database directly:

- `GET /terminals/` — list terminals (physical bus stands).
- `GET /terminals/{terminal_id}/departures?trip_date=YYYY-MM-DD` — the board itself: bay, single destination, departure time, live status, per row. Sourced from one `Route` per board destination (each route has its own `board_destination` and `origin_terminal_id`).
- `GET /terminals/trips/{trip_id}/board` — tap-through detail for one row: fare, bus, operator, and the **full** ordered stop list (this is where intermediate/"via" stops belong — never on the board itself).

Reverse-direction travel (e.g. Jalandhar → Ludhiana when the seeded route is Ludhiana → Jalandhar) is modeled as **a separate `Route`** departing from its own terminal, per Option A in the roadmap doc — not a single bidirectional route. `seed_data.py` demonstrates this with `Ludhiana - Jalandhar` and `Jalandhar - Ludhiana` as two distinct routes/terminals.

**Note on stop naming:** `/buses/journey` and the fare/ticket endpoints match stops by exact name (case-insensitive). Seed data names the Ludhiana-Jalandhar route's endpoint stops "Ludhiana" / "Jalandhar" — matching what a passenger would actually type — rather than the terminal's full display name ("Ludhiana Bus Stand"). A real deployment needs the location/stop-search layer described as gap #17 in the roadmap doc (fuzzy matching, aliases, nearby-stop resolution) so "Ludhiana", "Ludhiana Bus Stand", and "LDH" all resolve to the same stop.

## Important product limitation

The backend does **not** claim to have live GPS for every Punjab bus. It supports official/operator GPS when an authorized feed exists and a smartphone-driver/participant fallback for the prototype. Real operator integrations, payment settlement, POS installation, and fleet-wide live data require operator/transport-agency cooperation and applicable permissions.
