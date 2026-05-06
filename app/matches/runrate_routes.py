from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.database import models

from app.matches.match_service import resolve_match

router = APIRouter(prefix="/runrate")


@router.get("/{match_id}")
def runrate_graph(
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
            models.Ball.innings_id == innings.id
        ).order_by(
            models.Ball.created_at.asc()
        ).all()

        total = 0

        graph = []

        legal = 0

        for ball in balls:

            total += (
                ball.runs +
                ball.extra_runs
            )

            if ball.is_legal_ball:
                legal += 1

            overs = legal / 6

            rr = 0

            if overs > 0:
                rr = round(total / overs, 2)

            graph.append({
                "over_ball":
                    f"{ball.over}.{ball.ball}",

                "score":
                    total,

                "runrate":
                    rr
            })

        response.append({
            "innings":
                innings.innings_no,

            "graph":
                graph
        })

    return response