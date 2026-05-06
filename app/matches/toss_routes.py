from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.database import models

from app.matches.match_service import resolve_match

router = APIRouter(prefix="/toss")


@router.post("/{match_id}")
def save_toss(
        match_id: str,
        toss_winner_team_id: str,
        toss_decision: str,
        db: Session = Depends(get_db)
):
    match = resolve_match(db, match_id)

    match.toss_winner_team_id = (
        toss_winner_team_id
    )

    match.toss_decision = toss_decision

    db.commit()

    return {
        "message": "Toss updated"
    }


@router.get("/{match_id}")
def toss_details(
        match_id: str,
        db: Session = Depends(get_db)
):
    match = resolve_match(db, match_id)

    return {
        "toss_winner_team_id":
            match.toss_winner_team_id,

        "decision":
            match.toss_decision
    }