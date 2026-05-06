from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.database import models

router = APIRouter(prefix="/matches-list")


@router.get("/")
def all_matches(
        db: Session = Depends(get_db)
):
    matches = db.query(models.Match).order_by(
        models.Match.created_at.desc()
    ).all()

    response = []

    for match in matches:

        innings = db.query(models.MatchInnings).filter(
            models.MatchInnings.match_id == match.id
        ).all()

        response.append({

            "match_id":
                match.id,

            "team_a":
                match.teamA.name if match.teamA else None,

            "team_b":
                match.teamB.name if match.teamB else None,

            "status":
                match.status,

            "result":
                match.result,

            "innings": [
                {
                    "innings":
                        i.innings_no,

                    "score":
                        f"{i.runs}/{i.wickets}",

                    "overs":
                        i.overs
                }
                for i in innings
            ]
        })

    return response