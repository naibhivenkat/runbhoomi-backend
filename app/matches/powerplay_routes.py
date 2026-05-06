from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.database import models

from app.matches.match_service import resolve_match
from app.matches.innings_service import get_current_innings

router = APIRouter(prefix="/powerplay")


@router.get("/{match_id}")
def powerplay_score(
        match_id: str,
        db: Session = Depends(get_db)
):
    match = resolve_match(db, match_id)

    innings = get_current_innings(db, match.id)

    balls = db.query(models.Ball).filter(
        models.Ball.innings_id == innings.id
    ).all()

    pp_runs = 0

    pp_wickets = 0

    for ball in balls:

        if ball.over < 6:

            pp_runs += (
                ball.runs +
                ball.extra_runs
            )

            if ball.is_wicket:
                pp_wickets += 1

    return {
        "runs": pp_runs,
        "wickets": pp_wickets
    }