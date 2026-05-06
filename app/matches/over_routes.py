from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import models
from app.database.db import get_db

from app.matches.match_service import resolve_match
from app.matches.innings_service import get_current_innings

router = APIRouter(prefix="/overs")


@router.get("/{match_id}/current")
def current_over(
        match_id: str,
        db: Session = Depends(get_db)
):
    match = resolve_match(db, match_id)

    innings = get_current_innings(db, match.id)

    balls = db.query(models.Ball).filter(
        models.Ball.innings_id == innings.id
    ).order_by(
        models.Ball.created_at.desc()
    ).limit(6).all()

    balls.reverse()

    return {
        "over": [
            {
                "runs": ball.runs,

                "extra_type":
                    ball.extra_type,

                "wicket":
                    ball.is_wicket
            }
            for ball in balls
        ]
    }


@router.get("/{match_id}/all")
def all_overs(
        match_id: str,
        db: Session = Depends(get_db)
):
    match = resolve_match(db, match_id)

    innings = get_current_innings(db, match.id)

    balls = db.query(models.Ball).filter(
        models.Ball.innings_id == innings.id
    ).order_by(
        models.Ball.created_at.asc()
    ).all()

    overs = {}

    for ball in balls:

        over_key = str(ball.over)

        if over_key not in overs:
            overs[over_key] = []

        overs[over_key].append({
            "ball": ball.ball,
            "runs": ball.runs,
            "extra_type": ball.extra_type,
            "wicket": ball.is_wicket
        })

    return overs