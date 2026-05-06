from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.database import models
from app.database.models import generate_uuid


def resolve_match(db: Session, match_or_fixture_id: str):
    match = db.query(models.Match).filter(
        models.Match.id == match_or_fixture_id
    ).first()

    if match:
        return match

    fixture = db.query(models.TournamentMatch).filter(
        models.TournamentMatch.id == match_or_fixture_id
    ).first()

    if fixture and fixture.match_id:
        match = db.query(models.Match).filter(
            models.Match.id == fixture.match_id
        ).first()

    if not match:
        raise HTTPException(404, "Match not found")

    return match


def create_match_from_fixture(
        db: Session,
        fixture,
        user_id,
        overs
):
    match = models.Match(
        id=generate_uuid(),
        team_a_id=fixture.team_a_id,
        team_b_id=fixture.team_b_id,
        total_overs=overs,
        status="scheduled",
        tournament_id=fixture.tournament_id,
        admin_id=user_id,
        fixture_id=fixture.id
    )

    db.add(match)
    db.flush()

    fixture.match_id = match.id

    return match