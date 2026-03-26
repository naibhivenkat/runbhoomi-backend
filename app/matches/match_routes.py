from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
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


# @router.get("/get_matches")
# def get_matches(email: str, db: Session = Depends(get_db)):
#     player = db.query(models.Player).filter(models.Player.email == email).first()
#
#     if not player or not player.team_id:
#         return []
#
#     matches = db.query(models.Match).filter(
#         (models.Match.teamA_id == player.team_id) |
#         (models.Match.teamB_id == player.team_id)
#     ).all()
#
#     result = []
#
#     for match in matches:
#         team1 = db.query(models.Team).filter(models.Team.id == match.team1_id).first()
#         team2 = db.query(models.Team).filter(models.Team.id == match.team2_id).first()
#
#         total_runs = db.query(func.coalesce(func.sum(models.Ball.runs), 0)) \
#             .filter(models.Ball.match_id == match.id) \
#             .scalar()
#
#         wickets = db.query(func.count(models.Ball.id)) \
#             .filter(
#             models.Ball.match_id == match.id,
#             models.Ball.is_wicket == True
#         ).scalar()
#
#         last_ball = db.query(models.Ball) \
#             .filter(models.Ball.match_id == match.id) \
#             .order_by(models.Ball.over.desc(), models.Ball.ball.desc()) \
#             .first()
#
#         overs_text = f"{last_ball.over}.{last_ball.ball}" if last_ball else "0.0"
#
#         result.append({
#             "id": match.id,
#             "teamA": team1.name if team1 else "Team A",
#             "teamB": team2.name if team2 else "Team B",
#             "score": f"{total_runs}/{wickets} ({overs_text} ov)",
#             "status": match.status
#         })
#
#     return result

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