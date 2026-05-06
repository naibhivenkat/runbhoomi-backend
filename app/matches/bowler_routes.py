from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import models
from app.database.db import get_db
from app.database.models import generate_uuid
from app.matches.innings_service import get_current_innings
from app.matches.match_service import resolve_match

router = APIRouter(prefix="/bowler")


@router.post("/{match_id}/change")
def change_bowler(
        match_id: str,
        bowler_id: str,
        db: Session = Depends(get_db)
):
    match = resolve_match(db, match_id)

    innings = get_current_innings(db, match.id)

    player = db.query(models.Player).get(bowler_id)

    if not player:
        raise HTTPException(404, "Bowler not found")

    existing = db.query(models.Bowler).filter(
        models.Bowler.innings_id == innings.id,
        models.Bowler.player_id == bowler_id
    ).first()

    if existing:
        return {
            "message": "Bowler changed",
            "bowler": existing.name
        }

    bowler = models.Bowler(
        id=generate_uuid(),
        match_id=match.id,
        innings_id=innings.id,
        player_id=player.id,
        team_id=innings.bowling_team_id,
        name=player.name
    )

    db.add(bowler)

    db.commit()

    return {
        "message": "Bowler changed",
        "bowler": bowler.name
    }