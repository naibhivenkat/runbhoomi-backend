from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import models
from app.database.db import get_db

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


# @router.get("/{match_id}")
# def get_match_detail(match_id: int, db: Session = Depends(get_db)):
#     match = db.query(models.Match).options(
#         joinedload(models.Match.teamA),
#         joinedload(models.Match.teamB)
#     ).filter(models.Match.id == match_id).first()
#
#     if not match:
#         raise HTTPException(status_code=404, detail="Match not found")
#
#     return {
#         "id": match.id,
#
#         "team1": match.teamA.name if match.teamA else "",
#         "team2": match.teamB.name if match.teamB else "",
#
#         "score1": match.scoreA or "",
#         "score2": match.scoreB or "",
#
#         "overs1": match.oversA or "",
#         "overs2": match.oversB or "",
#
#         "status": match.status or "",
#
#         "note": match.note or "",
#     }
#
#
# @router.get("/{match_id}/live")
# def get_live_score(match_id: int, db: Session = Depends(get_db)):
#     match = db.query(models.Match).filter(
#         models.Match.id == match_id
#     ).first()
#
#     if not match:
#         raise HTTPException(status_code=404, detail="Match not found")
#
#     # 🔥 batsmen (striker first)
#     batsmen = db.query(models.Batsman).filter(
#         models.Batsman.match_id == match_id,
#         models.Batsman.is_out == False
#     ).order_by(models.Batsman.is_striker.desc()).all()
#
#     # 🔥 current bowler
#     bowler = db.query(models.Bowler).filter(
#         models.Bowler.match_id == match_id
#     ).order_by(models.Bowler.id.desc()).first()
#
#     # 🔥 partnership
#     total_runs = sum(b.runs or 0 for b in batsmen)
#     total_balls = sum(b.balls or 0 for b in batsmen)
#
#     # 🔥 extras (placeholder)
#     extras = 0
#
#     # 🔥 SAFE RUN RATE CALCULATION
#     def calculate_run_rate(score, overs):
#         try:
#             runs = int((score or "0/0").split("/")[0])
#
#             if not overs or "." not in overs:
#                 return 0
#
#             over_part, ball_part = overs.split(".")
#             total_overs = int(over_part) + int(ball_part) / 6
#
#             if total_overs == 0:
#                 return 0
#
#             return round(runs / total_overs, 2)
#
#         except:
#             return 0
#
#     run_rate = calculate_run_rate(match.scoreA, match.oversA)
#
#     return {
#         "score": match.scoreA or "",
#         "overs": match.oversA or "",
#         "status": match.status or "",
#
#         "batsmen": [
#             {
#                 "name": b.name,
#                 "runs": b.runs or 0,
#                 "balls": b.balls or 0,
#                 "fours": b.fours or 0,
#                 "sixes": b.sixes or 0,
#
#                 # ✅ dynamic strike rate
#                 "sr": round((b.runs / b.balls) * 100, 1) if b.balls else 0,
#
#                 "is_striker": b.is_striker
#             }
#             for b in batsmen
#         ],
#
#         "bowler": {
#             "name": bowler.name if bowler else "",
#             "overs": bowler.overs if bowler else "",
#             "runs": bowler.runs if bowler else 0,
#             "wickets": bowler.wickets if bowler else 0,
#             "eco": bowler.economy if bowler else 0,
#         },
#
#         "extras": extras,
#
#         "partnership": {
#             "runs": total_runs,
#             "balls": total_balls
#         },
#
#         "run_rate": run_rate
#     }
#
#

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from app.database.db import get_db
from app.database import models

router = APIRouter()


# 🔹 MATCH DETAIL
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


# 🔥 LIVE SCORE
@router.get("/{match_id}/live")
def get_live_score(match_id: int, db: Session = Depends(get_db)):
    match = db.query(models.Match).filter(
        models.Match.id == match_id
    ).first()

    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    # ✅ FIX 1: handle NULL is_out + match_id issue
    batsmen = db.query(models.Batsman).filter(
        models.Batsman.match_id == match_id,
        or_(
            models.Batsman.is_out == False,
            models.Batsman.is_out == None
        )
    ).order_by(models.Batsman.is_striker.desc()).all()

    # ✅ DEBUG (remove later)
    if not batsmen:
        print(f"⚠️ No batsmen found for match_id={match_id}")

    # 🔥 current bowler
    bowler = db.query(models.Bowler).filter(
        models.Bowler.match_id == match_id
    ).order_by(models.Bowler.id.desc()).first()

    # 🔥 partnership
    total_runs = sum((b.runs or 0) for b in batsmen)
    total_balls = sum((b.balls or 0) for b in batsmen)

    extras = 0  # placeholder


    # 🔥 SAFE RUN RATE CALCULATION
    def calculate_run_rate(score, overs):
        try:
            runs = int((score or "0/0").split("/")[0])

            if not overs or "." not in overs:
                return 0

            over_part, ball_part = overs.split(".")
            total_overs = int(over_part) + int(ball_part) / 6

            if total_overs == 0:
                return 0

            return round(runs / total_overs, 2)

        except Exception as e:
            print("Run rate error:", e)
            return 0


    run_rate = calculate_run_rate(match.scoreA, match.oversA)

    # ✅ FIX 2: fallback batsmen (VERY IMPORTANT)
    if not batsmen:
        batsmen_response = [
            {
                "name": "Yet to bat",
                "runs": 0,
                "balls": 0,
                "fours": 0,
                "sixes": 0,
                "sr": 0,
                "is_striker": False
            }
        ]
    else:
        batsmen_response = [
            {
                "name": b.name or "Unknown",   # ✅ FIX 3
                "runs": b.runs or 0,
                "balls": b.balls or 0,
                "fours": b.fours or 0,
                "sixes": b.sixes or 0,
                "sr": round((b.runs / b.balls) * 100, 1) if b.balls else 0,
                "is_striker": b.is_striker or False
            }
            for b in batsmen
        ]


    return {
        "score": match.scoreA or "",
        "overs": match.oversA or "",
        "status": match.status or "",

        "batsmen": batsmen_response,

        "bowler": {
            "name": bowler.name if bowler and bowler.name else "N/A",
            "overs": bowler.overs if bowler else "",
            "runs": bowler.runs if bowler else 0,
            "wickets": bowler.wickets if bowler else 0,
            "eco": bowler.economy if bowler else 0,
        },

        "extras": extras,

        "partnership": {
            "runs": total_runs,
            "balls": total_balls
        },

        "run_rate": run_rate
    }
