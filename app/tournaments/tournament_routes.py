from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import models
from app.database.db import get_db

router = APIRouter(prefix="/tournaments")

class TournamentCreate(BaseModel):
    name: str
    format: str
    overs: int
@router.post("/create")
def create_tournament(data: TournamentCreate, db: Session = Depends(get_db)):
    t = models.Tournament(
        name=data.name,
        format=data.format,
        overs=data.overs
    )
    db.add(t)
    db.commit()
    db.refresh(t)

    return {"id": t.id, "message": "Tournament created"}

@router.post("/{tournament_id}/add_team")
def add_team(tournament_id: int, team_id: int, db: Session = Depends(get_db)):
    tt = models.TournamentTeam(
        tournament_id=tournament_id,
        team_id=team_id
    )
    db.add(tt)
    db.commit()

    return {"message": "Team added"}


@router.get("/")
def get_tournaments(db: Session = Depends(get_db)):
    tournaments = db.query(models.Tournament).all()

    return [
        {
            "id": t.id,
            "name": t.name,
            "format": t.format,
            "overs": t.overs
        }
        for t in tournaments
    ]


@router.get("/")
def get_tournaments(db: Session = Depends(get_db)):
    tournaments = db.query(models.Tournament).all()

    return [
        {
            "id": t.id,
            "name": t.name,
            "format": t.format,
            "overs": t.overs
        }
        for t in tournaments
    ]
