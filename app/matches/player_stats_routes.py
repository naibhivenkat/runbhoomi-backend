from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.database import models

router = APIRouter(prefix="/player-stats")


@router.get("/{player_id}")
def player_stats(
        player_id: str,
        db: Session = Depends(get_db)
):
    batting = db.query(models.Batsman).filter(
        models.Batsman.player_id == player_id
    ).all()

    bowling = db.query(models.Bowler).filter(
        models.Bowler.player_id == player_id
    ).all()

    total_runs = sum(b.runs for b in batting)

    total_balls = sum(b.balls for b in batting)

    total_fours = sum(b.fours for b in batting)

    total_sixes = sum(b.sixes for b in batting)

    total_wickets = sum(b.wickets for b in bowling)

    total_bowling_runs = sum(
        b.runs for b in bowling
    )

    total_overs = 0

    for b in bowling:

        overs = b.overs.split(".")

        total_overs += (
            int(overs[0]) +
            (int(overs[1]) / 6)
        )

    strike_rate = 0

    if total_balls > 0:
        strike_rate = round(
            (total_runs / total_balls) * 100,
            2
        )

    economy = 0

    if total_overs > 0:
        economy = round(
            total_bowling_runs / total_overs,
            2
        )

    return {

        "batting": {

            "runs":
                total_runs,

            "balls":
                total_balls,

            "fours":
                total_fours,

            "sixes":
                total_sixes,

            "strike_rate":
                strike_rate
        },

        "bowling": {

            "wickets":
                total_wickets,

            "runs":
                total_bowling_runs,

            "overs":
                round(total_overs, 1),

            "economy":
                economy
        }
    }