# from datetime import datetime
#
# from fastapi import APIRouter, Depends, HTTPException
# from sqlalchemy import or_, func
# from sqlalchemy.orm import Session, joinedload
#
# from app.database import models
# from app.database.db import get_db
#
# router = APIRouter(prefix="/matches")
#
#
# @router.post("/create")
# def create_match(team1: int, team2: int, overs: int, db: Session = Depends(get_db)):
#     match = models.Match(team1_id=team1, team2_id=team2, overs=overs, status="scheduled")
#     db.add(match)
#     db.commit()
#     return {"match_id": match.id}
#
#
# @router.get("/get_matches")
# def get_matches(email: str, db: Session = Depends(get_db)):
#     player = db.query(models.Player).filter(
#         models.Player.email == email
#     ).first()
#
#     if not player or not player.team_id:
#         return []
#
#     matches = db.query(models.Match).filter(
#         (models.Match.team_a_id == player.team_id) |
#         (models.Match.team_b_id == player.team_id)
#     ).all()
#
#     result = []
#
#     for m in matches:
#         teamA = db.query(models.Team).filter(
#             models.Team.id == m.teamA_id
#         ).first()
#
#         teamB = db.query(models.Team).filter(
#             models.Team.id == m.teamB_id
#         ).first()
#
#         result.append({
#             "id": m.id,
#             "teamA": teamA.name if teamA else "",
#             "teamB": teamB.name if teamB else "",
#             "scoreA": f"{m.scoreA} ({m.oversA} ov)" if m.scoreA else "",
#             "scoreB": f"{m.scoreB} ({m.oversB} ov)" if m.scoreB else "",
#             "status": m.status,
#             "note": m.note
#         })
#
#     return result
#
#
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
# # @router.get("/{match_id}/live")
# # def get_live_score(match_id: int, db: Session = Depends(get_db)):
# #     match = db.query(models.Match).filter(
# #         models.Match.id == match_id
# #     ).first()
# #
# #     if not match:
# #         raise HTTPException(status_code=404, detail="Match not found")
# #
# #     # ✅ FIX 1: handle NULL is_out + match_id issue
# #     batsmen = db.query(models.Batsman).filter(
# #         models.Batsman.match_id == match_id,
# #         or_(
# #             models.Batsman.is_out == False,
# #             models.Batsman.is_out == None
# #         )
# #     ).order_by(models.Batsman.is_striker.desc()).all()
# #
# #     # ✅ DEBUG (remove later)
# #     if not batsmen:
# #         print(f"⚠️ No batsmen found for match_id={match_id}")
# #
# #     # 🔥 current bowler
# #     bowler = db.query(models.Bowler).filter(
# #         models.Bowler.match_id == match_id
# #     ).order_by(models.Bowler.id.desc()).first()
# #
# #     # 🔥 partnership
# #     total_runs = sum((b.runs or 0) for b in batsmen)
# #     total_balls = sum((b.balls or 0) for b in batsmen)
# #
# #     extras = 0  # placeholder
# #
# #     # 🔥 SAFE RUN RATE CALCULATION
# #     def calculate_run_rate(score, overs):
# #         try:
# #             runs = int((score or "0/0").split("/")[0])
# #
# #             if not overs or "." not in overs:
# #                 return 0
# #
# #             over_part, ball_part = overs.split(".")
# #             total_overs = int(over_part) + int(ball_part) / 6
# #
# #             if total_overs == 0:
# #                 return 0
# #
# #             return round(runs / total_overs, 2)
# #
# #         except Exception as e:
# #             print("Run rate error:", e)
# #             return 0
# #
# #     run_rate = calculate_run_rate(match.scoreA, match.oversA)
# #
# #     # ✅ FIX 2: fallback batsmen (VERY IMPORTANT)
# #     if not batsmen:
# #         batsmen_response = [
# #             {
# #                 "name": "Yet to bat",
# #                 "runs": 0,
# #                 "balls": 0,
# #                 "fours": 0,
# #                 "sixes": 0,
# #                 "sr": 0,
# #                 "is_striker": False
# #             }
# #         ]
# #     else:
# #         batsmen_response = [
# #             {
# #                 "name": b.name or "Unknown",  # ✅ FIX 3
# #                 "runs": b.runs or 0,
# #                 "balls": b.balls or 0,
# #                 "fours": b.fours or 0,
# #                 "sixes": b.sixes or 0,
# #                 "sr": round((b.runs / b.balls) * 100, 1) if b.balls else 0,
# #                 "is_striker": b.is_striker or False
# #             }
# #             for b in batsmen
# #         ]
# #
# #     return {
# #         "score": match.scoreA or "",
# #         "overs": match.oversA or "",
# #         "status": match.status or "",
# #
# #         "batsmen": batsmen_response,
# #
# #         "bowler": {
# #             "name": bowler.name if bowler and bowler.name else "N/A",
# #             "overs": bowler.overs if bowler else "",
# #             "runs": bowler.runs if bowler else 0,
# #             "wickets": bowler.wickets if bowler else 0,
# #             "eco": bowler.economy if bowler else 0,
# #         },
# #
# #         "extras": extras,
# #
# #         "partnership": {
# #             "runs": total_runs,
# #             "balls": total_balls
# #         },
# #
# #         "run_rate": run_rate
# #     }
#
# # @router.get("/{match_id}/live")
# # def get_live_score(match_id: int, db: Session = Depends(get_db)):
# #     match = db.query(models.Match).filter(
# #         models.Match.id == match_id
# #     ).first()
# #
# #     if not match:
# #         raise HTTPException(status_code=404, detail="Match not found")
# #
# #     # 🔥 GET ALL BALLS
# #     balls = db.query(models.Ball).filter(
# #         models.Ball.match_id == match_id
# #     ).order_by(models.Ball.id.asc()).all()
# #
# #     # ✅ LAST OVER (LAST 6 BALLS)
# #     last_balls = []
# #     for b in balls[-6:]:
# #         if b.is_wicket:
# #             last_balls.append("W")
# #         else:
# #             last_balls.append(str(b.runs or 0))
# #
# #     # ✅ TOTAL RUNS
# #     total_runs = sum((b.runs or 0) + (b.extra_runs or 0) for b in balls)
# #
# #     # ✅ WICKETS
# #     wickets = sum(1 for b in balls if b.is_wicket)
# #
# #     # ✅ LEGAL BALLS
# #     legal_balls = sum(
# #         1 for b in balls if b.extra_type not in ["wide", "no_ball"]
# #     )
# #
# #     overs_display = f"{legal_balls // 6}.{legal_balls % 6}"
# #
# #     score = f"{total_runs}/{wickets}"
# #
# #     # 🔥 BATSMEN (same as your existing logic)
# #     batsmen = db.query(models.Batsman).filter(
# #         models.Batsman.match_id == match_id,
# #         or_(
# #             models.Batsman.is_out == False,
# #             models.Batsman.is_out == None
# #         )
# #     ).order_by(models.Batsman.is_striker.desc()).all()
# #
# #     batsmen_response = [
# #         {
# #             "name": b.name or "Unknown",
# #             "runs": b.runs or 0,
# #             "balls": b.balls or 0,
# #             "fours": b.fours or 0,
# #             "sixes": b.sixes or 0,
# #             "sr": round((b.runs / b.balls) * 100, 1) if b.balls else 0,
# #             "is_striker": b.is_striker or False
# #         }
# #         for b in batsmen
# #     ] if batsmen else [{
# #         "name": "Yet to bat",
# #         "runs": 0,
# #         "balls": 0,
# #         "fours": 0,
# #         "sixes": 0,
# #         "sr": 0,
# #         "is_striker": False
# #     }]
# #
# #     # 🔥 BOWLER
# #     bowler = db.query(models.Bowler).filter(
# #         models.Bowler.match_id == match_id
# #     ).order_by(models.Bowler.id.desc()).first()
# #
# #     return {
# #         "score": score,
# #         "overs": overs_display,
# #         "status": match.status or "Live",
# #
# #         "last_over": last_balls,  # ✅🔥 THIS FIXES YOUR UI
# #
# #         "batsmen": batsmen_response,
# #
# #         "bowler": {
# #             "name": bowler.name if bowler else "N/A",
# #             "overs": bowler.overs if bowler else "",
# #             "runs": bowler.runs if bowler else 0,
# #             "wickets": bowler.wickets if bowler else 0,
# #             "eco": bowler.economy if bowler else 0,
# #         },
# #
# #         "extras": 0,
# #         "run_rate": 0
# #     }
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
#     balls = db.query(models.Ball).filter(
#         models.Ball.match_id == match_id
#     ).order_by(models.Ball.id.asc()).all()
#
#     # 🔥 SCORE
#     total_runs = sum((b.runs or 0) + (b.extra_runs or 0) for b in balls)
#     wickets = sum(1 for b in balls if b.is_wicket)
#
#     # 🔥 BALLS
#     legal_balls = sum(
#         1 for b in balls if b.extra_type not in ["wide", "no_ball"]
#     )
#
#     overs = f"{legal_balls // 6}.{legal_balls % 6}"
#     score = f"{total_runs}/{wickets}"
#
#     # 🔥 LAST OVER
#     last_over = []
#     for b in balls[-6:]:
#         if b.is_wicket:
#             last_over.append("W")
#         else:
#             last_over.append(str(b.runs or 0))
#
#     # 🔥 BATSMEN
#     batsmen = db.query(models.Batsman).filter(
#         models.Batsman.match_id == match_id,
#         or_(
#             models.Batsman.is_out == False,
#             models.Batsman.is_out == None
#         )
#     ).order_by(models.Batsman.is_striker.desc()).all()
#
#     batsmen_response = [
#         {
#             "name": b.name or "Unknown",
#             "runs": b.runs or 0,
#             "balls": b.balls or 0,
#             "fours": b.fours or 0,
#             "sixes": b.sixes or 0,
#             "sr": round((b.runs / b.balls) * 100, 1) if b.balls else 0,
#             "is_striker": b.is_striker or False
#         }
#         for b in batsmen
#     ] if batsmen else [{
#         "name": "Yet to bat",
#         "runs": 0,
#         "balls": 0,
#         "fours": 0,
#         "sixes": 0,
#         "sr": 0,
#         "is_striker": False
#     }]
#
#     # 🔥 BOWLER
#     bowler = db.query(models.Bowler).filter(
#         models.Bowler.match_id == match_id
#     ).order_by(models.Bowler.id.desc()).first()
#
#     # 🔥 RUN RATE
#     run_rate = round(total_runs / (legal_balls / 6), 2) if legal_balls else 0
#
#     return {
#         "score": score,
#         "overs": overs,
#         "status": match.status or "Live",
#
#         "last_over": last_over,
#
#         "batsmen": batsmen_response,
#
#         "bowler": {
#             "name": bowler.name if bowler else "N/A",
#             "overs": bowler.overs if bowler else "",
#             "runs": bowler.runs if bowler else 0,
#             "wickets": bowler.wickets if bowler else 0,
#             "eco": bowler.economy if bowler else 0,
#         },
#
#         "extras": 0,
#         "run_rate": run_rate
#     }
#
# @router.post("/{match_id}/add_ball")
# def add_ball(
#         match_id: int,
#         runs: int = 0,
#         wicket: bool = False,
#         extra_type: str = None,  # wide, no_ball, bye, leg_bye
#         extra_runs: int = 0,
#         db: Session = Depends(get_db)
# ):
#     # ✅ Validate match
#     match = db.query(models.Match).filter(models.Match.id == match_id).first()
#     if not match:
#         raise HTTPException(status_code=404, detail="Match not found")
#
#     # ✅ Validate extra_type
#     valid_extras = ["wide", "no_ball", "bye", "leg_bye", None]
#     if extra_type not in valid_extras:
#         raise HTTPException(status_code=400, detail="Invalid extra type")
#
#     # ✅ Get last ball
#     last_ball = db.query(models.Ball).filter(
#         models.Ball.match_id == match_id
#     ).order_by(models.Ball.id.desc()).first()
#
#     # Default start
#     over = 0
#     ball = 1
#
#     if last_ball:
#         over = last_ball.over
#         ball = last_ball.ball
#
#         # ❗ Only increment ball for legal deliveries
#         if extra_type not in ["wide", "no_ball"]:
#             ball += 1
#
#             if ball > 6:
#                 over += 1
#                 ball = 1
#
#     # ✅ Calculate total runs for this delivery
#     total_runs = runs + extra_runs
#
#     # Wide / no-ball always give at least 1 run
#     if extra_type in ["wide", "no_ball"] and total_runs == 0:
#         total_runs = 1
#
#     # ✅ Create ball
#     new_ball = models.Ball(
#         match_id=match_id,
#         over=over,
#         ball=ball,
#         runs=runs,
#         extra_type=extra_type,
#         extra_runs=extra_runs,
#         is_wicket=wicket,
#         created_at=datetime.utcnow()
#     )
#
#     try:
#         db.add(new_ball)
#         db.commit()
#         db.refresh(new_ball)
#     except Exception as e:
#         db.rollback()
#         raise HTTPException(status_code=500, detail=str(e))
#
#     # ✅ Score calculation
#     total_runs_match = db.query(func.sum(
#         models.Ball.runs + models.Ball.extra_runs
#     )).filter(
#         models.Ball.match_id == match_id
#     ).scalar() or 0
#
#     wickets = db.query(models.Ball).filter(
#         models.Ball.match_id == match_id,
#         models.Ball.is_wicket == True
#     ).count()
#
#     # ✅ Balls count (exclude wides & no-balls)
#     legal_balls = db.query(models.Ball).filter(
#         models.Ball.match_id == match_id,
#         models.Ball.extra_type.notin_(["wide", "no_ball"])
#     ).count()
#
#     overs_display = f"{legal_balls // 6}.{legal_balls % 6}"
#
#     return {
#         "message": "Ball added",
#         "data": {
#             "over": new_ball.over,
#             "ball": new_ball.ball,
#             "runs": total_runs,
#             "is_wicket": wicket,
#             "extra_type": extra_type,
#             "score": f"{total_runs_match}/{wickets}",
#             "overs": overs_display
#         }
#     }
#
#
# @router.get("/{match_id}/last_ball")
# def get_last_balls(match_id: int, db: Session = Depends(get_db)):
#     balls = db.query(models.Ball).filter(
#         models.Ball.match_id == match_id
#     ).order_by(models.Ball.id.desc()).limit(6).all()
#
#     last_balls = []
#
#     # reverse so order = old → new
#     for b in reversed(balls):
#         if b.is_wicket:
#             last_balls.append("W")
#         else:
#             last_balls.append(str(b.runs or 0))
#
#     return {
#         "lastBalls": last_balls
#     }




from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, func
from sqlalchemy.orm import Session, joinedload

from app.database import models
from app.database.db import get_db

router = APIRouter(prefix="/matches")


@router.post("/create")
def create_match(team1: int, team2: int, overs: int, db: Session = Depends(get_db)):
    match = models.Match(
        team_a_id=team1,
        team_b_id=team2,
        total_overs=overs,
        status="scheduled"
    )
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

    matches = db.query(models.Match).options(
        joinedload(models.Match.teamA),
        joinedload(models.Match.teamB)
    ).filter(
        (models.Match.team_a_id == player.team_id) |
        (models.Match.team_b_id == player.team_id)
    ).all()

    result = []

    for m in matches:
        result.append({
            "id": m.id,
            "teamA": m.teamA.name if m.teamA else "",
            "teamB": m.teamB.name if m.teamB else "",
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


@router.get("/{match_id}/live")
def get_live_score(match_id: int, db: Session = Depends(get_db)):
    match = db.query(models.Match).filter(
        models.Match.id == match_id
    ).first()

    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    balls = db.query(models.Ball).filter(
        models.Ball.match_id == match_id
    ).order_by(models.Ball.id.asc()).all()

    total_runs = sum((b.runs or 0) + (b.extra_runs or 0) for b in balls)
    wickets = sum(1 for b in balls if b.is_wicket)

    legal_balls = sum(
        1 for b in balls if b.extra_type not in ["wide", "no_ball"]
    )

    overs = f"{legal_balls // 6}.{legal_balls % 6}"
    score = f"{total_runs}/{wickets}"

    last_over = []
    for b in balls[-6:]:
        last_over.append("W" if b.is_wicket else str(b.runs or 0))

    batsmen = db.query(models.Batsman).filter(
        models.Batsman.match_id == match_id,
        or_(
            models.Batsman.is_out == False,
            models.Batsman.is_out == None
        )
    ).order_by(models.Batsman.is_striker.desc()).all()

    batsmen_response = [
        {
            "name": b.name or "Unknown",
            "runs": b.runs or 0,
            "balls": b.balls or 0,
            "fours": b.fours or 0,
            "sixes": b.sixes or 0,
            "sr": round((b.runs / b.balls) * 100, 1) if b.balls else 0,
            "is_striker": b.is_striker or False
        }
        for b in batsmen
    ] if batsmen else [{
        "name": "Yet to bat",
        "runs": 0,
        "balls": 0,
        "fours": 0,
        "sixes": 0,
        "sr": 0,
        "is_striker": False
    }]

    bowler = db.query(models.Bowler).filter(
        models.Bowler.match_id == match_id
    ).order_by(models.Bowler.id.desc()).first()

    run_rate = round(total_runs / (legal_balls / 6), 2) if legal_balls else 0

    return {
        "score": score,
        "overs": overs,
        "status": match.status or "Live",
        "last_over": last_over,
        "batsmen": batsmen_response,
        "bowler": {
            "name": bowler.name if bowler else "N/A",
            "overs": bowler.overs if bowler else "",
            "runs": bowler.runs if bowler else 0,
            "wickets": bowler.wickets if bowler else 0,
            "eco": bowler.economy if bowler else 0,
        },
        "extras": 0,
        "run_rate": run_rate
    }


@router.post("/{match_id}/add_ball")
def add_ball(
        match_id: int,
        runs: int = 0,
        wicket: bool = False,
        extra_type: str = None,
        extra_runs: int = 0,
        db: Session = Depends(get_db)
):
    match = db.query(models.Match).filter(models.Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    valid_extras = ["wide", "no_ball", "bye", "leg_bye", None]
    if extra_type not in valid_extras:
        raise HTTPException(status_code=400, detail="Invalid extra type")

    last_ball = db.query(models.Ball).filter(
        models.Ball.match_id == match_id
    ).order_by(models.Ball.id.desc()).first()

    over = 0
    ball = 1

    if last_ball:
        over = last_ball.over
        ball = last_ball.ball

        if extra_type not in ["wide", "no_ball"]:
            ball += 1
            if ball > 6:
                over += 1
                ball = 1

    total_runs = runs + extra_runs

    if extra_type in ["wide", "no_ball"] and total_runs == 0:
        total_runs = 1

    new_ball = models.Ball(
        match_id=match_id,
        over=over,
        ball=ball,
        runs=runs,
        extra_type=extra_type,
        extra_runs=extra_runs,
        is_wicket=wicket,
        created_at=datetime.utcnow()
    )

    try:
        db.add(new_ball)
        db.commit()
        db.refresh(new_ball)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    total_runs_match = db.query(func.sum(
        models.Ball.runs + models.Ball.extra_runs
    )).filter(
        models.Ball.match_id == match_id
    ).scalar() or 0

    wickets = db.query(models.Ball).filter(
        models.Ball.match_id == match_id,
        models.Ball.is_wicket == True
    ).count()

    legal_balls = db.query(models.Ball).filter(
        models.Ball.match_id == match_id,
        models.Ball.extra_type.notin_(["wide", "no_ball"])
    ).count()

    overs_display = f"{legal_balls // 6}.{legal_balls % 6}"

    return {
        "message": "Ball added",
        "data": {
            "over": new_ball.over,
            "ball": new_ball.ball,
            "runs": total_runs,
            "is_wicket": wicket,
            "extra_type": extra_type,
            "score": f"{total_runs_match}/{wickets}",
            "overs": overs_display
        }
    }


@router.get("/{match_id}/last_ball")
def get_last_balls(match_id: int, db: Session = Depends(get_db)):
    balls = db.query(models.Ball).filter(
        models.Ball.match_id == match_id
    ).order_by(models.Ball.id.desc()).limit(6).all()

    last_balls = []

    for b in reversed(balls):
        last_balls.append("W" if b.is_wicket else str(b.runs or 0))

    return {
        "lastBalls": last_balls
    }
