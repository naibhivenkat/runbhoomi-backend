from fastapi import APIRouter,Depends
from sqlalchemy.orm import Session
from app.database.db import get_db
from app.database import models
from app.auth.jwt_handler import create_token

router=APIRouter(prefix="/auth")

@router.post("/register")
def register(email:str,password:str,db:Session=Depends(get_db)):
    user=models.User(email=email,password_hash=password)
    db.add(user)
    db.commit()
    return {"message":"user created"}

@router.post("/login")
def login(email:str,password:str,db:Session=Depends(get_db)):
    user=db.query(models.User).filter(models.User.email==email).first()
    if not user:
        return {"error":"user not found"}
    token=create_token(user.id)
    return {"token":token}
