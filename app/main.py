import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers import routes, buses, tickets, gps, crowd, auth_router, terminals

# Create tables on startup (fine for SQLite/demo; use Alembic migrations for production)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="YatraGPT Backend",
    description="Real-time public bus travel intelligence platform API",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("YATRAGPT_CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",") if origin.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(routes.router)
app.include_router(buses.router)
app.include_router(tickets.router)
app.include_router(gps.router)
app.include_router(crowd.router)
app.include_router(terminals.router)


@app.get("/")
def root():
    return {"message": "YatraGPT backend is running", "docs": "/docs"}
