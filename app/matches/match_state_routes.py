from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.database import models

from app.matches.match_service import resolve_match
from app.matches.innings_service import (
    get_current_innings
)

router = APIRouter(prefix="/state")


@router.get("/{match_id}")
def match_state(
        match_id: str,
        db: Session = Depends(get_db)
):
    match = resolve_match(db, match_id)

    innings = None

    if match.status != "completed":

        innings = get_current_innings(
            db,
            match.id
        )

    return {

        "match_id":
            match.id,

        "status":
            match.status,

        "innings":
            innings.innings_no if innings else None,

        "target":
            match.target,

        "result":
            match.result,

        "winner_team_id":
            match.winner_team_id
    }