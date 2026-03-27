from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from app.database.db import get_db
from app.database import models
from sqlalchemy import func

router = APIRouter(prefix="/matches")


@router.post("/create")
def create_match(team1: int, team2: int, overs: int, db: Session = Depends(get_db)):
    match = models.Match(team1_id=team1, team2_id=team2, overs=overs, status="scheduled")
    db.add(match)
    db.commit()
    return {"match_id": match.id}



@router.get("/get_matches")
def get_matches(email: str, db: Session = Depends(get_db)):

    player = db.query(models.Player).filter(
        models.Player.email == email
    ).first()

    if not player or not player.team_id:
        return []

    matches = db.query(models.Match).filter(
        (models.Match.teamA_id == player.team_id) |
        (models.Match.teamB_id == player.team_id)
    ).all()

    result = []

    for m in matches:
        teamA = db.query(models.Team).filter(
            models.Team.id == m.teamA_id
        ).first()

        teamB = db.query(models.Team).filter(
            models.Team.id == m.teamB_id
        ).first()

        result.append({
            "id": m.id,
            "teamA": teamA.name if teamA else "",
            "teamB": teamB.name if teamB else "",
            "scoreA": f"{m.scoreA} ({m.oversA} ov)" if m.scoreA else "",
            "scoreB": f"{m.scoreB} ({m.oversB} ov)" if m.scoreB else "",
            "status": m.status,
            "note": m.note
        })

    return result


@router.get("/{match_id}")
def get_match_detail(match_id: int, db: Session = Depends(get_db)):

    match = db.query(models.Match).options(
        joinedload(models.Match.teamA),
        joinedload(models.Match.teamB)
    ).filter(models.Match.id == match_id).first()

    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    return {
        "id": match.id,

        "team1": match.teamA.name if match.teamA else "",
        "team2": match.teamB.name if match.teamB else "",

        "score1": match.scoreA or "",
        "score2": match.scoreB or "",

        "overs1": match.oversA or "",
        "overs2": match.oversB or "",

        "status": match.status or "",

        "note": match.note or "",
    }