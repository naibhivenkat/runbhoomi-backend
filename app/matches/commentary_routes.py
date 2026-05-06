from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.database import models

from app.matches.match_service import resolve_match

router = APIRouter(prefix="/commentary")


@router.get("/{match_id}")
def commentary(
        match_id: str,
        innings_no: int = None,
        limit: int = 50,
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
            models.Ball.created_at.desc()
        ).limit(limit).all()

        innings_commentary = []

        for ball in reversed(balls):

            text = ""

            if ball.is_wicket:

                text = (
                    f"WICKET! "
                    f"{ball.wicket_type or 'OUT'}"
                )

            elif ball.extra_type:

                if ball.extra_type == "wide":
                    text = f"WIDE + {ball.runs}"

                elif ball.extra_type == "no_ball":
                    text = f"NO BALL + {ball.runs}"

                elif ball.extra_type == "bye":
                    text = f"BYE {ball.runs}"

                elif ball.extra_type == "legbye":
                    text = f"LEG BYE {ball.runs}"

            else:

                if ball.runs == 4:
                    text = "FOUR!"

                elif ball.runs == 6:
                    text = "SIX!"

                elif ball.runs == 0:
                    text = "DOT BALL"

                else:
                    text = f"{ball.runs} RUNS"

            innings_commentary.append({

                "ball":
                    f"{ball.over}.{ball.ball}",

                "commentary":
                    text,

                "runs":
                    ball.runs,

                "extra_type":
                    ball.extra_type,

                "wicket":
                    ball.is_wicket
            })

        response.append({

            "innings":
                innings.innings_no,

            "commentary":
                innings_commentary
        })

    return response