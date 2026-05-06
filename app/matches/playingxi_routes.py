from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.database import models
from app.database.models import generate_uuid

router = APIRouter(prefix="/playingxi")


@router.post("/{match_id}/add")
def add_playing_xi(
        match_id: str,
        player_id: str,
        team_id: str,
        db: Session = Depends(get_db)
):
    existing = db.query(models.PlayingXI).filter(
        models.PlayingXI.match_id == match_id,
        models.PlayingXI.player_id == player_id
    ).first()

    if existing:
        raise HTTPException(
            400,
            "Player already added"
        )

    xi = models.PlayingXI(
        id=generate_uuid(),
        match_id=match_id,
        player_id=player_id,
        team_id=team_id
    )

    db.add(xi)

    db.commit()

    return {
        "message": "Player added"
    }


@router.get("/{match_id}")
def get_playing_xi(
        match_id: str,
        db: Session = Depends(get_db)
):
    players = db.query(models.PlayingXI).filter(
        models.PlayingXI.match_id == match_id
    ).all()

    return [
        {
            "player_id": p.player_id,
            "team_id": p.team_id
        }
        for p in players
    ]