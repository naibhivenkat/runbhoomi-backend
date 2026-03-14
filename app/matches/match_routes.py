from fastapi import APIRouter,Depends
from sqlalchemy.orm import Session
from app.database.db import get_db
from app.database import models

router=APIRouter(prefix="/matches")

@router.post("/create")
def create_match(team1:int,team2:int,overs:int,db:Session=Depends(get_db)):
    match=models.Match(team1_id=team1,team2_id=team2,overs=overs,status="scheduled")
    db.add(match)
    db.commit()
    return {"match_id":match.id}
