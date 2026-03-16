import time
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.jwt_handler import create_token
from app.auth.otp_service import (
    generate_otp,
    save_otp,
    get_otp,
    delete_otp,
    increment_attempt
)
from app.database import models
from app.database.db import get_db
from app.utls.password_utils import hash_password

router=APIRouter(prefix="/auth")


@router.post("/player_register")
def create_player(data: dict, db: Session = Depends(get_db)):

    existing = db.query(models.Player).filter(models.Player.email == data["email"]).first()

    if existing:
        return {"error": "Email already registered"}

    hashed_pw = hash_password(data["password"])

    player = models.Player(
        name=data["name"],
        phone=data["phone"],
        email=data["email"],
        city=data["city"],
        role=data["role"],
        batting_style=data["batting_style"],
        bowling_style=data["bowling_style"],
        experience=int(data["experience"]),
        jersey_number=int(data["jersey_number"]),
        dob=datetime.fromisoformat(data["dob"]).date(),
        password_hash=hashed_pw
    )

    db.add(player)
    db.commit()
    db.refresh(player)

    token = create_token(player.id)

    return {
        "message": "player created",
        "token": token
    }

@router.post("/send_otp")
def send_otp(data: dict, db: Session = Depends(get_db)):

    email = data.get("email")

    if not email:
        return {"status": "error", "message": "Email required"}

    otp = generate_otp()

    save_otp(db, email, otp)

    # TODO send email here
    print("OTP:", otp)

    return {
        "status": "success",
        "message": "OTP sent"
    }


@router.post("/verify_otp")
def verify_otp(data: dict, db: Session = Depends(get_db)):

    email = data.get("email")
    otp_input = str(data.get("otp"))

    record = get_otp(db, email)

    if not record:
        return {"status": "error", "message": "No OTP sent"}

    if record.attempts >= 5:
        return {"status": "error", "message": "Too many attempts"}

    if int(time.time()) > record.expiry:
        return {"status": "error", "message": "OTP expired"}

    if record.otp == otp_input:

        delete_otp(db, email)

        return {
            "status": "success",
            "message": "OTP verified"
        }

    increment_attempt(db, record)

    return {
        "status": "error",
        "message": "Invalid OTP"
    }

@router.post("/login")
def login(email:str,password:str,db:Session=Depends(get_db)):
    user=db.query(models.User).filter(models.User.email==email).first()
    if not user:
        return {"error":"user not found"}
    token=create_token(user.id)
    return {"token":token}
