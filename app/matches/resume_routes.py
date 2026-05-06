from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import models
from app.database.db import get_db
from app.matches.innings_service import get_current_innings
from app.matches.match_service import resolve_match

router = APIRouter(prefix="/resume")


@router.get("/{match_id}")
def resume_match(
        match_id: str,
        db: Session = Depends(get_db)
):
    match = resolve_match(db, match_id)

    innings = get_current_innings(db, match.id)

    batsmen = db.query(models.Batsman).filter(
        models.Batsman.innings_id == innings.id,
        models.Batsman.is_out == False
    ).all()

    striker = next((b for b in batsmen if b.is_striker), None)

    non_striker = next((b for b in batsmen if not b.is_striker), None)

    last_ball = (
        db.query(models.Ball)
        .filter(models.Ball.innings_id == innings.id)
        .order_by(models.Ball.created_at.desc())
        .first()
    )

    return {
        "match_id": match.id,

        "innings": innings.innings_no,

        "score": f"{innings.runs}/{innings.wickets}",

        "overs": innings.overs,

        "target": innings.target,

        "striker": {
            "id": striker.player_id,
            "name": striker.name
        } if striker else None,

        "non_striker": {
            "id": non_striker.player_id,
            "name": non_striker.name
        } if non_striker else None,

        "current_bowler_id":
            last_ball.bowler_id if last_ball else None
    }