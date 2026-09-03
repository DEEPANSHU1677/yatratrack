import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# On Vercel, only /tmp is writable. For real production, use Postgres.
if os.getenv("VERCEL") or os.getenv("YATRAGPT_ENV") == "production":
    SQLALCHEMY_DATABASE_URL = "sqlite:////tmp/yatragpt.db"
else:
    SQLALCHEMY_DATABASE_URL = "sqlite:///./yatragpt.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
