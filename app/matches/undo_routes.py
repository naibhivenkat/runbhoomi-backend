from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import models
from app.database.db import get_db

from app.matches.match_service import resolve_match
from app.matches.innings_service import get_current_innings
from app.matches.scoring_service import recalculate_innings

router = APIRouter(prefix="/undo")





@router.delete("/{match_id}/last-ball")
def undo_last_ball(
        match_id: str,
        db: Session = Depends(get_db)
):
    match = resolve_match(db, match_id)

    innings = get_current_innings(db, match.id)

    last_ball = (
        db.query(models.Ball)
        .filter(models.Ball.innings_id == innings.id)
        .order_by(models.Ball.created_at.desc())
        .first()
    )

    if not last_ball:
        raise HTTPException(404, "No ball found")

    striker = db.query(models.Batsman).filter(
        models.Batsman.player_id == last_ball.batsman_id,
        models.Batsman.innings_id == innings.id
    ).first()

    if striker:
        if not last_ball.extra_type:
            striker.balls -= 1

        striker.runs -= last_ball.runs

        if last_ball.runs == 4:
            striker.fours -= 1

        if last_ball.runs == 6:
            striker.sixes -= 1

    if last_ball.is_wicket:
        striker.is_out = False

    db.delete(last_ball)

    recalculate_innings(db, innings)

    db.commit()

    return {
        "message": "Last ball undone"
    }