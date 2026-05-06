from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import models
from app.database.db import get_db
from app.matches.innings_service import get_current_innings
from app.matches.match_service import resolve_match

router = APIRouter(prefix="/live")


@router.get("/{match_id}")
def live_score(
        match_id: str,
        db: Session = Depends(get_db)
):
    match = resolve_match(db, match_id)

    innings = get_current_innings(db, match.id)

    batsmen = db.query(models.Batsman).filter(
        models.Batsman.innings_id == innings.id,
        models.Batsman.is_out == False
    ).all()

    return {
        "score": f"{innings.runs}/{innings.wickets}",
        "overs": innings.overs,
        "target": innings.target,
        "innings": innings.innings_no,
        "batsmen": [
            {
                "name": b.name,
                "runs": b.runs,
                "balls": b.balls
            }
            for b in batsmen
        ]
    }