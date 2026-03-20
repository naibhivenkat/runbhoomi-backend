import time
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi import Depends
from google.auth.transport import requests
from google.oauth2 import id_token
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.jwt_handler import create_token
from app.auth.otp_service import (
    generate_otp,
    save_otp,
    get_otp,
    delete_otp,
    increment_attempt,
    send_email_otp
)
from app.database import models
from app.database.db import get_db
from app.utls.password_utils import hash_password

router = APIRouter(prefix="/auth")

GOOGLE_CLIENT_ID = "830296224047-c6mftjed5a6ld7c6oa9k72rpeurgvfo5.apps.googleusercontent.com"
JWT_SECRET = "your_secret_key"


class GoogleAuthRequest(BaseModel):
    idToken: str


@router.post("/player_register")
def create_player(data: dict, db: Session = Depends(get_db)):

    if not data.get("email") or not data.get("password"):
        return {"status": "error", "message": "Missing required fields"}

    existing = db.query(models.Player).filter(
        models.Player.email == data["email"]
    ).first()

    if existing:
        return {"status": "error", "message": "Email already registered"}

    hashed_pw = hash_password(data["password"])

    player = models.Player(
        name=data["name"],
        phone=data["phone"],
        email=data["email"],
        gender=data.get("gender"),
        city=data.get("city"),
        role=data.get("role"),
        batting_style=data.get("batting_style"),
        bowling_style=data.get("bowling_style"),
        experience=int(data.get("experience", 0)),
        jersey_number=int(data.get("jersey_number", 0)),
        dob=datetime.fromisoformat(data["dob"]).date()
            if data.get("dob") else None,
        password_hash=hashed_pw,
        profile_photo=data.get("profile_photo"),
    )

    db.add(player)
    db.commit()
    db.refresh(player)

    token = create_token(player.id)

    return {
        "status": "success",
        "message": "player created",
        "token": token
    }


@router.post("/send_otp")
def send_otp(data: dict, db: Session = Depends(get_db)):

    email = data.get("email")

    if not email:
        return {
            "status": "error",
            "message": "Email required"
        }

    otp = generate_otp()

    save_otp(db, email, otp)

    if send_email_otp(email, otp):
        return {
            "status": "success",
            "message": "OTP sent successfully"
        }

    return {
        "status": "error",
        "message": "Failed to send OTP"
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
def login(email: str, password: str, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        return {"error": "user not found"}
    token = create_token(user.id)
    return {"token": token}


@router.post("/google")
def google_auth(data: GoogleAuthRequest, db: Session = Depends(get_db)):
    try:
        # ✅ Verify Google token
        idinfo = id_token.verify_oauth2_token(
            data.idToken,
            requests.Request(),
            GOOGLE_CLIENT_ID
        )

        email = idinfo.get("email")
        name = idinfo.get("name", "")
        picture = idinfo.get("picture", "")

        if not email:
            raise HTTPException(status_code=400, detail="Email not found")

        # ✅ Check if player already exists
        player = db.query(models.Player).filter(
            models.Player.email == email
        ).first()

        # ✅ If NOT exists → create new player
        if not player:
            player = models.Player(
                name=name,
                email=email,
                profile_photo=picture,
                phone=None,
                password_hash=None,  # 🔥 Google users don't need password
                created_at=datetime.utcnow()
            )

            db.add(player)
            db.commit()
            db.refresh(player)

        # ✅ Generate JWT using your existing function
        token = create_token(player.id)

        return {
            "status": "success",
            "token": token,
            "user": {
                "id": player.id,
                "email": player.email,
                "name": player.name,
                "profile_photo": player.profile_photo
            }
        }

    except Exception as e:
        print("Google Auth Error:", e)
        raise HTTPException(status_code=401, detail="Invalid Google token")