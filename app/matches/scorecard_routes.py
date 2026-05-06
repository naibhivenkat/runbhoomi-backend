from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import models
from app.database.db import get_db


router = APIRouter(prefix="/scorecard")


@router.get("/{match_id}")
def get_scorecard(
    match_id: str,
    db: Session = Depends(get_db)
):

    match = db.query(models.Match).filter(
        models.Match.id == match_id
    ).first()

    if not match:
        return {
            "error": "Match not found"
        }

    innings = db.query(
        models.MatchInnings
    ).filter(
        models.MatchInnings.match_id
        == match_id
    ).all()

    innings_data = []

    for inn in innings:

        batsmen = db.query(
            models.Batsman
        ).filter(
            models.Batsman.innings_id
            == inn.id
        ).all()

        bowlers = db.query(
            models.Bowler
        ).filter(
            models.Bowler.innings_id
            == inn.id
        ).all()

        innings_data.append({

            "innings_no":
                inn.innings_no,

            "score":
                f"{inn.runs}/{inn.wickets}",

            "overs":
                inn.overs,

            "batsmen": [
                {
                    "name": b.name,
                    "runs": b.runs,
                    "balls": b.balls,
                    "fours": b.fours,
                    "sixes": b.sixes,
                    "is_out": b.is_out
                }
                for b in batsmen
            ],

            "bowlers": [
                {
                    "name": b.name,
                    "overs": b.overs,
                    "runs": b.runs,
                    "wickets": b.wickets
                }
                for b in bowlers
            ]
        })

    return {
        "match_id": match.id,
        "status": match.status,
        "innings": innings_data
    }