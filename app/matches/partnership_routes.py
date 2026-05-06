from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import models
from app.database.db import get_db

from app.matches.match_service import resolve_match
from app.matches.innings_service import get_current_innings

router = APIRouter(prefix="/partnership")


@router.get("/{match_id}")
def current_partnership(
        match_id: str,
        db: Session = Depends(get_db)
):
    match = resolve_match(db, match_id)

    innings = get_current_innings(db, match.id)

    batsmen = db.query(models.Batsman).filter(
        models.Batsman.innings_id == innings.id,
        models.Batsman.is_out == False
    ).all()

    total_runs = sum(b.runs for b in batsmen)

    total_balls = sum(b.balls for b in batsmen)

    return {
        "runs": total_runs,

        "balls": total_balls,

        "batsmen": [
            {
                "name": b.name,
                "runs": b.runs,
                "balls": b.balls
            }
            for b in batsmen
        ]
    }