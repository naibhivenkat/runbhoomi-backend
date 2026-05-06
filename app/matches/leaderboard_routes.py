from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database.db import get_db
from app.database import models

router = APIRouter(prefix="/leaderboard")


@router.get("/batting")
def batting_leaderboard(
        limit: int = 10,
        db: Session = Depends(get_db)
):
    batsmen = db.query(
        models.Batsman
    ).order_by(
        desc(models.Batsman.runs)
    ).limit(limit).all()

    return [
        {
            "player_id": b.player_id,
            "name": b.name,
            "runs": b.runs
        }
        for b in batsmen
    ]


@router.get("/bowling")
def bowling_leaderboard(
        limit: int = 10,
        db: Session = Depends(get_db)
):
    bowlers = db.query(
        models.Bowler
    ).order_by(
        desc(models.Bowler.wickets)
    ).limit(limit).all()

    return [
        {
            "player_id": b.player_id,
            "name": b.name,
            "wickets": b.wickets
        }
        for b in bowlers
    ]