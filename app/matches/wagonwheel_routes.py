from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.database import models

router = APIRouter(prefix="/wagonwheel")


@router.get("/{player_id}")
def wagonwheel(
        player_id: str,
        db: Session = Depends(get_db)
):
    balls = db.query(models.Ball).filter(
        models.Ball.batsman_id == player_id
    ).all()

    return [
        {
            "runs": ball.runs,
            "over": ball.over,
            "ball": ball.ball
        }
        for ball in balls
    ]