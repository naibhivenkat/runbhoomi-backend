from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.database import models

from app.matches.match_service import resolve_match
from app.matches.innings_service import get_current_innings

router = APIRouter(prefix="/required")


@router.get("/{match_id}")
def required_runs(
        match_id: str,
        db: Session = Depends(get_db)
):
    match = resolve_match(db, match_id)

    innings = get_current_innings(db, match.id)

    if innings.innings_no != 2:
        return {
            "message": "Required runs only for chase"
        }

    target = innings.target or 0

    remaining_runs = target - innings.runs

    overs_split = innings.overs.split(".")

    completed_overs = int(overs_split[0])

    completed_balls = int(overs_split[1])

    total_balls = match.total_overs * 6

    used_balls = (
        completed_overs * 6
    ) + completed_balls

    remaining_balls = total_balls - used_balls

    rrr = 0

    if remaining_balls > 0:
        rrr = round(
            (remaining_runs * 6)
            / remaining_balls,
            2
        )

    return {
        "target": target,

        "score":
            innings.runs,

        "required":
            remaining_runs,

        "balls_left":
            remaining_balls,

        "required_run_rate":
            rrr
    }