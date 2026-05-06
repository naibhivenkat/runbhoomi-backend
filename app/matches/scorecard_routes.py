from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import models
from app.database.db import get_db
from app.matches.match_service import resolve_match

router = APIRouter(prefix="/scorecard")


@router.get("/{match_id}")
def scorecard(
        match_id: str,
        db: Session = Depends(get_db)
):
    match = resolve_match(db, match_id)

    innings_list = db.query(models.MatchInnings).filter(
        models.MatchInnings.match_id == match.id
    ).order_by(models.MatchInnings.innings_no.asc()).all()

    innings_data = []

    for innings in innings_list:
        batsmen = db.query(models.Batsman).filter(
            models.Batsman.innings_id == innings.id
        ).all()

        bowlers = db.query(models.Bowler).filter(
            models.Bowler.innings_id == innings.id
        ).all()

        innings_data.append({
            "innings": innings.innings_no,
            "score": f"{innings.runs}/{innings.wickets}",
            "overs": innings.overs,

            "batsmen": [
                {
                    "name": b.name,
                    "runs": b.runs,
                    "balls": b.balls,
                    "fours": b.fours,
                    "sixes": b.sixes
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
        "innings": innings_data
    }