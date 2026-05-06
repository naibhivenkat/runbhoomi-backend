from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import models
from app.database.db import get_db

from app.matches.match_service import resolve_match

router = APIRouter(prefix="/fow")


@router.get("/{match_id}")
def fall_of_wickets(
        match_id: str,
        db: Session = Depends(get_db)
):
    match = resolve_match(db, match_id)

    innings_list = db.query(
        models.MatchInnings
    ).filter(
        models.MatchInnings.match_id == match.id
    ).all()

    response = []

    for innings in innings_list:

        balls = db.query(models.Ball).filter(
            models.Ball.innings_id == innings.id,
            models.Ball.is_wicket == True
        ).order_by(
            models.Ball.created_at.asc()
        ).all()

        wickets = []

        total = 0

        wicket_no = 0

        for ball in balls:

            total += (
                ball.runs +
                ball.extra_runs
            )

            wicket_no += 1

            wickets.append({

                "wicket":
                    wicket_no,

                "score":
                    f"{total}/{wicket_no}",

                "player_out_id":
                    ball.player_out_id,

                "over":
                    f"{ball.over}.{ball.ball}"
            })

        response.append({
            "innings":
                innings.innings_no,

            "fow":
                wickets
        })

    return response