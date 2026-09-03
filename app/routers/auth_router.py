import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.auth import create_access_token, hash_password, verify_password
from app.database import get_db
from app.models import models
from app.schemas import schemas

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=schemas.UserOut)
def register(payload: schemas.UserRegister, db: Session = Depends(get_db)):
    """Public registration creates PASSENGER accounts only by default.

    Role registration may be enabled explicitly for a local/demo environment
    with YATRAGPT_ALLOW_DEMO_ROLE_REGISTRATION=1. Production deployments
    should provision staff accounts through an admin/operator workflow.
    """
    existing = db.query(models.User).filter(models.User.phone == payload.phone).first()
    if existing:
        raise HTTPException(400, "An account with this phone number already exists")

    allow_demo_roles = os.getenv("YATRAGPT_ALLOW_DEMO_ROLE_REGISTRATION", "0") == "1"
    role = payload.role if allow_demo_roles else models.UserRole.PASSENGER

    if role in (models.UserRole.DRIVER, models.UserRole.CONDUCTOR) and not payload.assigned_bus_id:
        raise HTTPException(400, f"{role.value} accounts must specify assigned_bus_id")

    if payload.assigned_bus_id:
        bus = db.query(models.Bus).filter(models.Bus.id == payload.assigned_bus_id).first()
        if not bus:
            raise HTTPException(404, "Assigned bus not found")
        if role not in (models.UserRole.DRIVER, models.UserRole.CONDUCTOR):
            raise HTTPException(400, "assigned_bus_id is only valid for DRIVER/CONDUCTOR accounts")

    user = models.User(
        name=payload.name.strip(),
        phone=payload.phone.strip(),
        hashed_password=hash_password(payload.password),
        role=role,
        assigned_bus_id=payload.assigned_bus_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.phone == form_data.username.strip()).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(401, "Incorrect phone number or password")

    token = create_access_token(user_id=user.id, role=user.role.value)
    return schemas.Token(access_token=token, role=user.role)
