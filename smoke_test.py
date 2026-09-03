"""Small integration smoke test. Run from the project root after seed_data.py."""
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import models

client = TestClient(app)

def login(phone, password):
    r = client.post('/auth/login', data={'username': phone, 'password': password})
    assert r.status_code == 200, r.text
    return r.json()['access_token']

passenger_token = login('9999999999', 'passenger123')
driver_token = login('9999999998', 'driver123')

r = client.get('/buses/journey', params={'origin': 'Jalandhar', 'destination': 'Pathankot', 'trip_date': '2026-08-28'})
assert r.status_code == 200, r.text
journey = r.json()[0]
assert journey['buses'], journey
route_id = journey['route_id']
trip_id = journey['buses'][0]['trip_id']
bus_number = journey['buses'][0]['bus_vehicle_number']

r = client.get(f'/routes/{route_id}/fare', params={'from_stop': 'Jalandhar', 'to_stop': 'Mukerian'})
assert r.status_code == 200, r.text
assert r.json()['fare'] == 90

headers = {'Authorization': f'Bearer {passenger_token}'}
r = client.post('/tickets/', json={
    'route_id': route_id,
    'passenger_name': 'ignored-by-server',
    'origin_stop': 'Jalandhar',
    'destination_stop': 'Pathankot',
}, headers=headers)
assert r.status_code == 200, r.text
ticket_id = r.json()['id']
assert r.json()['passenger_name'] == 'Demo Passenger'

r = client.post('/tickets/board', json={
    'ticket_id': ticket_id,
    'vehicle_number': bus_number,
    'trip_date': '2026-08-28',
}, headers=headers)
assert r.status_code == 200, r.text
trip_id = r.json()['trip_id']

# Passenger GPS must be authenticated, own the ticket, and have boarded.
r = client.post('/gps/ping', json={
    'trip_id': trip_id,
    'source': 'passenger',
    'ticket_id': ticket_id,
    'lat': 31.40,
    'lng': 75.52,
}, headers=headers)
assert r.status_code == 200, r.text

r = client.post('/gps/ping', json={
    'trip_id': trip_id,
    'source': 'bus_device',
    'lat': 31.41,
    'lng': 75.51,
}, headers={'Authorization': f'Bearer {driver_token}'})
assert r.status_code == 200, r.text
assert r.json()['current_estimate']['method'] == 'official_bus_gps'

r = client.post('/crowd/report', json={'trip_id': trip_id, 'ticket_id': ticket_id, 'level': 'MEDIUM'}, headers=headers)
assert r.status_code == 200, r.text

live = client.get(f'/gps/trip/{trip_id}/live')
assert live.status_code == 200, live.text
assert live.json()['current_lat'] is not None

# --- Departure board (Terminal -> Departure Board -> tap-through) ---
r = client.get('/terminals/')
assert r.status_code == 200, r.text
ludhiana = next(t for t in r.json() if t['city'] == 'Ludhiana')

r = client.get(f'/terminals/{ludhiana["id"]}/departures', params={'trip_date': '2026-08-28'})
assert r.status_code == 200, r.text
board = r.json()
assert len(board) >= 6, board
# Board must show ONE destination per row, never a "via" list.
assert all(' via ' not in row['destination'].lower() for row in board)

jalandhar_row = next(row for row in board if row['destination'] == 'Jalandhar')
r = client.get(f'/terminals/trips/{jalandhar_row["trip_id"]}/board')
assert r.status_code == 200, r.text
detail = r.json()
assert detail['route']['stops'][0]['name'] == 'Ludhiana'
assert detail['route']['stops'][-1]['name'] == 'Jalandhar'
assert len(detail['route']['stops']) > 2  # full via-stop detail lives here, not on the board

# Reverse direction is a separate Route (Option A), and it must also work.
r = client.get('/buses/journey', params={'origin': 'Jalandhar', 'destination': 'Ludhiana', 'trip_date': '2026-08-28'})
assert r.status_code == 200, r.text

print('SMOKE TEST PASSED')
