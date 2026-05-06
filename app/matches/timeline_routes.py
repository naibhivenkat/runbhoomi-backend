from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import models
from app.database.db import get_db

from app.matches.match_service import resolve_match

router = APIRouter(prefix="/timeline")


@router.get("/{match_id}")
def match_timeline(
        match_id: str,
        innings_no: int = None,
        db: Session = Depends(get_db)
):
    match = resolve_match(db, match_id)

    innings_query = db.query(
        models.MatchInnings
    ).filter(
        models.MatchInnings.match_id == match.id
    )

    if innings_no:
        innings_query = innings_query.filter(
            models.MatchInnings.innings_no == innings_no
        )

    innings_list = innings_query.all()

    response = []

    for innings in innings_list:

        balls = db.query(models.Ball).filter(
            models.Ball.innings_id == innings.id
        ).order_by(
            models.Ball.created_at.asc()
        ).all()

        response.append({
            "innings": innings.innings_no,

            "score":
                f"{innings.runs}/{innings.wickets}",

            "overs":
                innings.overs,

            "timeline": [
                {
                    "over": ball.over,

                    "ball": ball.ball,

                    "runs": ball.runs,

                    "extra_type":
                        ball.extra_type,

                    "extra_runs":
                        ball.extra_runs,

                    "wicket":
                        ball.is_wicket,

                    "wicket_type":
                        ball.wicket_type,

                    "batsman_id":
                        ball.batsman_id,

                    "bowler_id":
                        ball.bowler_id
                }
                for ball in balls
            ]
        })

    return response