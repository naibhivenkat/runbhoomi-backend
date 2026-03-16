from fastapi import APIRouter,Depends
from sqlalchemy.orm import Session
from app.database.db import get_db
from app.database import models
from app.auth.jwt_handler import create_token
from datetime import datetime

router=APIRouter(prefix="/auth")

@router.post("/player_register")
def create_player(data: dict, db: Session = Depends(get_db)):

    player = models.Player(
        name=data["name"],
        phone=data["phone"],
        email=data["email"],
        city=data["city"],
        role=data["role"],
        batting_style=data["batting_style"],
        bowling_style=data["bowling_style"],
        experience=data["experience"],
        jersey_number=data["jersey_number"],
        dob=datetime.fromisoformat(data["dob"])
    )

    db.add(player)
    db.commit()

    return {"message": "player created"}

@router.post("/login")
def login(email:str,password:str,db:Session=Depends(get_db)):
    user=db.query(models.User).filter(models.User.email==email).first()
    if not user:
        return {"error":"user not found"}
    token=create_token(user.id)
    return {"token":token}
