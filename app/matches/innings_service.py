from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.database import models
from app.database.models import generate_uuid


def get_current_innings(db: Session, match_id: str):
    innings = (
        db.query(models.MatchInnings)
        .filter(
            models.MatchInnings.match_id == match_id,
            models.MatchInnings.status == "live"
        )
        .order_by(models.MatchInnings.innings_no.desc())
        .first()
    )

    if not innings:
        raise HTTPException(404, "Active innings not found")

    return innings


def create_first_innings(
        db: Session,
        match,
        batting_team_id: str,
        bowling_team_id: str
):
    innings = models.MatchInnings(
        id=generate_uuid(),
        match_id=match.id,
        innings_no=1,
        batting_team_id=batting_team_id,
        bowling_team_id=bowling_team_id,
        status="live"
    )

    db.add(innings)
    db.flush()

    return innings


def create_second_innings(
        db: Session,
        match,
        innings1
):
    innings2 = models.MatchInnings(
        id=generate_uuid(),
        match_id=match.id,
        innings_no=2,
        batting_team_id=innings1.bowling_team_id,
        bowling_team_id=innings1.batting_team_id,
        target=innings1.runs + 1,
        status="live"
    )

    db.add(innings2)

    match.target = innings1.runs + 1
    match.current_innings = 2

    db.flush()

    return innings2


def complete_innings(db: Session, innings):
    innings.status = "completed"
    db.flush()


def calculate_innings_score(db: Session, innings_id: str):
    balls = db.query(models.Ball).filter(
        models.Ball.innings_id == innings_id
    ).all()

    runs = sum((b.runs or 0) + (b.extra_runs or 0) for b in balls)

    wickets = sum(1 for b in balls if b.is_wicket)

    legal_balls = sum(1 for b in balls if b.is_legal_ball)

    overs = f"{legal_balls // 6}.{legal_balls % 6}"

    return {
        "runs": runs,
        "wickets": wickets,
        "overs": overs
    }