from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import models
from app.database.db import get_db

from app.matches.match_service import resolve_match

router = APIRouter(prefix="/stats")


@router.get("/{match_id}")
def match_stats(
        match_id: str,
        db: Session = Depends(get_db)
):
    match = resolve_match(db, match_id)

    innings_list = db.query(
        models.MatchInnings
    ).filter(
        models.MatchInnings.match_id == match.id
    ).all()

    innings_stats = []

    for innings in innings_list:

        balls = db.query(models.Ball).filter(
            models.Ball.innings_id == innings.id
        ).all()

        fours = sum(
            1 for b in balls if b.runs == 4
        )

        sixes = sum(
            1 for b in balls if b.runs == 6
        )

        extras = sum(
            b.extra_runs for b in balls
        )

        wickets = sum(
            1 for b in balls if b.is_wicket
        )

        innings_stats.append({

            "innings":
                innings.innings_no,

            "runs":
                innings.runs,

            "wickets":
                wickets,

            "overs":
                innings.overs,

            "fours":
                fours,

            "sixes":
                sixes,

            "extras":
                extras
        })

    return {
        "match_id": match.id,
        "stats": innings_stats
    }