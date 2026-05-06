from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import models
from app.database.db import get_db

from app.matches.match_service import resolve_match
from app.matches.innings_service import (
    get_current_innings,
    create_second_innings,
    complete_innings
)

router = APIRouter(prefix="/innings")


@router.post("/{match_id}/end")
def end_innings(
        match_id: str,
        striker_id: str = None,
        non_striker_id: str = None,
        bowler_id: str = None,
        db: Session = Depends(get_db)
):
    match = resolve_match(db, match_id)

    innings = get_current_innings(db, match.id)

    complete_innings(db, innings)

    # =====================================================
    # FIRST INNINGS COMPLETE
    # =====================================================

    if innings.innings_no == 1:

        innings2 = create_second_innings(
            db,
            match,
            innings
        )

        # ==============================================
        # INITIAL BATSMEN
        # ==============================================

        if striker_id and non_striker_id:

            striker_player = db.query(
                models.Player
            ).get(striker_id)

            non_striker_player = db.query(
                models.Player
            ).get(non_striker_id)

            db.add(models.Batsman(
                match_id=match.id,
                innings_id=innings2.id,
                player_id=striker_player.id,
                team_id=innings2.batting_team_id,
                name=striker_player.name,
                is_striker=True
            ))

            db.add(models.Batsman(
                match_id=match.id,
                innings_id=innings2.id,
                player_id=non_striker_player.id,
                team_id=innings2.batting_team_id,
                name=non_striker_player.name,
                is_striker=False
            ))

        # ==============================================
        # INITIAL BOWLER
        # ==============================================

        if bowler_id:

            bowler_player = db.query(
                models.Player
            ).get(bowler_id)

            db.add(models.Bowler(
                match_id=match.id,
                innings_id=innings2.id,
                player_id=bowler_player.id,
                team_id=innings2.bowling_team_id,
                name=bowler_player.name
            ))

        match.status = "innings_break"

        db.commit()

        return {
            "message": "First innings completed",
            "target": innings2.target,
            "next_innings": 2
        }

    # =====================================================
    # SECOND INNINGS COMPLETE
    # =====================================================

    match.status = "completed"

    db.commit()

    return {
        "message": "Match completed"
    }