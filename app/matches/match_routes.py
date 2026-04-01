# from datetime import datetime
#
# from fastapi import APIRouter, Depends, HTTPException
# from sqlalchemy import or_, func
# from sqlalchemy.orm import Session, joinedload
#
# from app.database import models
# from app.database.db import get_db
# from app.database.models import TournamentPoints, TournamentMatch
#
# router = APIRouter(prefix="/matches")
#
#
# @router.post("/create_match")
# def create_match(
#         team_a_id: int,
#         team_b_id: int,
#         overs: int = 20,
#         db: Session = Depends(get_db)
# ):
#     match = models.Match(
#         teamA_id=team_a_id,
#         teamB_id=team_b_id,
#         total_overs=overs,
#         status="created"
#     )
#
#     db.add(match)
#     db.commit()
#     db.refresh(match)
#
#     return {
#         "match_id": match.id,
#         "message": "Match created"
#     }
#
#
# @router.post("/add_player_to_team")
# def add_player_to_team(
#         team_id: int,
#         player_id: int,
#         db: Session = Depends(get_db)
# ):
#     tp = models.TeamPlayer(
#         team_id=team_id,
#         player_id=player_id
#     )
#
#     db.add(tp)
#     db.commit()
#
#     return {"message": "Player added to team"}
#
#
# @router.post("/{match_id}/set_playing_xi")
# def set_playing_xi(
#         match_id: int,
#         team_id: int,
#         player_ids: list[int],
#         db: Session = Depends(get_db)
# ):
#     if len(player_ids) != 11:
#         raise HTTPException(status_code=400, detail="Must select 11 players")
#
#     # clear existing XI
#     db.query(models.PlayingXI).filter(
#         models.PlayingXI.match_id == match_id,
#         models.PlayingXI.team_id == team_id
#     ).delete()
#
#     for pid in player_ids:
#         xi = models.PlayingXI(
#             match_id=match_id,
#             team_id=team_id,
#             player_id=pid
#         )
#         db.add(xi)
#
#     db.commit()
#
#     return {"message": "Playing XI set"}
#
#
# @router.post("/{match_id}/start_match")
# def start_match(
#         match_id: int,
#         striker_id: int,
#         non_striker_id: int,
#         bowler_name: str,
#         db: Session = Depends(get_db)
# ):
#     match = db.query(models.Match).filter(
#         models.Match.id == match_id
#     ).first()
#
#     if not match:
#         raise HTTPException(status_code=404, detail="Match not found")
#
#     # clear old batsmen
#     db.query(models.Batsman).filter(
#         models.Batsman.match_id == match_id
#     ).delete()
#
#     # create striker
#     striker = models.Batsman(
#         match_id=match_id,
#         name=f"Player {striker_id}",
#         is_striker=True
#     )
#
#     # create non-striker
#     non_striker = models.Batsman(
#         match_id=match_id,
#         name=f"Player {non_striker_id}",
#         is_striker=False
#     )
#
#     db.add_all([striker, non_striker])
#
#     # create bowler
#     bowler = models.Bowler(
#         match_id=match_id,
#         name=bowler_name,
#         overs="0.0",
#         runs=0,
#         wickets=0,
#         economy=0
#     )
#
#     db.add(bowler)
#
#     # set match live
#     match.status = "Live"
#
#     db.commit()
#
#     return {"message": "Match started"}
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
#     matches = db.query(models.Match).options(
#         joinedload(models.Match.teamA),
#         joinedload(models.Match.teamB)
#     ).filter(
#         (models.Match.team_a_id == player.team_id) |
#         (models.Match.team_b_id == player.team_id)
#     ).all()
#
#     result = []
#
#     for m in matches:
#         result.append({
#             "id": m.id,
#             "teamA": m.teamA.name if m.teamA else "",
#             "teamB": m.teamB.name if m.teamB else "",
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
#         "team1": match.teamA.name if match.teamA else "",
#         "team2": match.teamB.name if match.teamB else "",
#         "score1": match.scoreA or "",
#         "score2": match.scoreB or "",
#         "overs1": match.oversA or "",
#         "overs2": match.oversB or "",
#         "status": match.status or "",
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
#     balls = db.query(models.Ball).filter(
#         models.Ball.match_id == match_id
#     ).order_by(models.Ball.id.asc()).all()
#
#     total_runs = sum((b.runs or 0) + (b.extra_runs or 0) for b in balls)
#     wickets = sum(1 for b in balls if b.is_wicket)
#
#     legal_balls = sum(
#         1 for b in balls if b.extra_type not in ["wide", "no_ball"]
#     )
#
#     overs = f"{legal_balls // 6}.{legal_balls % 6}"
#     score = f"{total_runs}/{wickets}"
#
#     last_over = []
#     for b in balls[-6:]:
#         last_over.append("W" if b.is_wicket else str(b.runs or 0))
#
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
#     bowler = db.query(models.Bowler).filter(
#         models.Bowler.match_id == match_id
#     ).order_by(models.Bowler.id.desc()).first()
#
#     run_rate = round(total_runs / (legal_balls / 6), 2) if legal_balls else 0
#
#     return {
#         "score": score,
#         "overs": overs,
#         "status": match.status or "Live",
#         "last_over": last_over,
#         "batsmen": batsmen_response,
#         "bowler": {
#             "name": bowler.name if bowler else "N/A",
#             "overs": bowler.overs if bowler else "",
#             "runs": bowler.runs if bowler else 0,
#             "wickets": bowler.wickets if bowler else 0,
#             "eco": bowler.economy if bowler else 0,
#         },
#         "extras": 0,
#         "run_rate": run_rate
#     }
#
#
# @router.post("/{match_id}/add_ball")
# def add_ball(
#         match_id: int,
#         runs: int = 0,
#         wicket: bool = False,
#         extra_type: str = None,
#         extra_runs: int = 0,
#         db: Session = Depends(get_db)
# ):
#     match = db.query(models.Match).filter(models.Match.id == match_id).first()
#     if not match:
#         raise HTTPException(status_code=404, detail="Match not found")
#
#     valid_extras = ["wide", "no_ball", "bye", "leg_bye", None]
#     if extra_type not in valid_extras:
#         raise HTTPException(status_code=400, detail="Invalid extra type")
#
#     last_ball = db.query(models.Ball).filter(
#         models.Ball.match_id == match_id
#     ).order_by(models.Ball.id.desc()).first()
#
#     over = 0
#     ball = 1
#
#     if last_ball:
#         over = last_ball.over
#         ball = last_ball.ball
#
#         if extra_type not in ["wide", "no_ball"]:
#             ball += 1
#             if ball > 6:
#                 over += 1
#                 ball = 1
#
#     total_runs = runs + extra_runs
#
#     if extra_type in ["wide", "no_ball"] and total_runs == 0:
#         total_runs = 1
#
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
#     for b in reversed(balls):
#         last_balls.append("W" if b.is_wicket else str(b.runs or 0))
#
#     return {
#         "lastBalls": last_balls
#     }
#
#
# @router.post("/{match_id}/result")
# def update_result(
#         match_id: int,
#         winner: str,
#         runs_scored: int,
#         overs: float,
#         db: Session = Depends(get_db)
# ):
#     match = db.query(TournamentMatch).get(match_id)
#     match.winner = winner
#
#     # update points
#     teams = [match.team_a, match.team_b]
#
#     for team in teams:
#         p = db.query(TournamentPoints).filter_by(
#             tournament_id=match.tournament_id,
#             team_name=team
#         ).first()
#
#         p.played += 1
#
#         if team == winner:
#             p.wins += 1
#             p.points += 2
#             p.runs_scored += runs_scored
#             p.overs_faced += overs
#         else:
#             p.losses += 1
#             p.runs_conceded += runs_scored
#             p.overs_bowled += overs
#
#     db.commit()
#
#     return {"message": "Result updated"}


from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, func
from sqlalchemy.orm import Session, joinedload

from app.database import models
from app.database.db import get_db
from app.database.models import TournamentPoints, TournamentMatch

router = APIRouter(prefix="/matches")


# =========================
# CREATE MATCH
# =========================
@router.post("/create_match")
def create_match(team_a_id: int, team_b_id: int, overs: int = 20,
                 db: Session = Depends(get_db)):
    match = models.Match(
        team_a_id=team_a_id,
        team_b_id=team_b_id,
        total_overs=overs,
        status="created"
    )
    db.add(match)
    db.commit()
    db.refresh(match)

    return {"match_id": match.id, "message": "Match created"}


# =========================
# START MATCH
# =========================
@router.post("/{match_id}/start_match")
def start_match(match_id: int, striker_id: int,
                non_striker_id: int, bowler_name: str,
                db: Session = Depends(get_db)):

    match = db.query(models.Match).filter(
        models.Match.id == match_id
    ).first()

    if not match:
        raise HTTPException(404, "Match not found")

    db.query(models.Batsman).filter(
        models.Batsman.match_id == match_id
    ).delete()

    striker = models.Batsman(
        match_id=match_id,
        name=f"Player {striker_id}",
        is_striker=True
    )

    non_striker = models.Batsman(
        match_id=match_id,
        name=f"Player {non_striker_id}",
        is_striker=False
    )

    bowler = models.Bowler(
        match_id=match_id,
        name=bowler_name,
        overs="0.0",
        runs=0,
        wickets=0,
        economy=0
    )

    db.add_all([striker, non_striker, bowler])

    # ✅ FIX: lowercase status
    match.status = "live"

    db.commit()

    return {"message": "Match started"}


# =========================
# GET MATCHES (🔥 FIXED)
# =========================
@router.get("/get_matches")
def get_matches(email: str, db: Session = Depends(get_db)):

    player = db.query(models.Player).filter(
        models.Player.email == email
    ).first()

    if not player or not player.team_id:
        # 🔥 TEMP: return all matches if user not mapped
        matches = db.query(models.Match).options(
            joinedload(models.Match.teamA),
            joinedload(models.Match.teamB)
        ).all()
    else:
        matches = db.query(models.Match).options(
            joinedload(models.Match.teamA),
            joinedload(models.Match.teamB)
        ).filter(
            (models.Match.team_a_id == player.team_id) |
            (models.Match.team_b_id == player.team_id)
        ).all()

    result = []

    for m in matches:

        # 🔥 LIVE CALCULATION
        balls = db.query(models.Ball).filter(
            models.Ball.match_id == m.id
        ).all()

        total_runs = sum((b.runs or 0) + (b.extra_runs or 0) for b in balls)
        wickets = sum(1 for b in balls if b.is_wicket)

        legal_balls = sum(
            1 for b in balls if b.extra_type not in ["wide", "no_ball"]
        )

        overs = f"{legal_balls // 6}.{legal_balls % 6}"

        live_score = f"{total_runs}/{wickets}" if balls else ""
        note = ""

        if m.current_innings == 2:
            note = m.note
        elif m.current_innings == 1:
            note = f"{m.teamA.name} batting"
        result.append({
            "id": m.id,
            "teamA": m.teamA.name if m.teamA else "",
            "teamB": m.teamB.name if m.teamB else "",

            # ✅ FIX: live vs completed
            "scoreA": live_score if m.status == "live" else (
                f"{m.scoreA} ({m.oversA})" if m.scoreA else ""
            ),

            "scoreB": f"{m.scoreB} ({m.oversB})" if m.scoreB else "",

            "overs": overs if m.status == "live" else m.oversA,

            "status": m.status,

            # ✅ FIX: always keep note
            "note": note})

    return result


# =========================
# MATCH DETAIL
# =========================
@router.get("/{match_id}")
def get_match_detail(match_id: int, db: Session = Depends(get_db)):

    match = db.query(models.Match).options(
        joinedload(models.Match.teamA),
        joinedload(models.Match.teamB)
    ).filter(models.Match.id == match_id).first()

    if not match:
        raise HTTPException(404, "Match not found")

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


# =========================
# LIVE SCORE (🔥 FIXED)
# =========================
@router.get("/{match_id}/live")
def get_live_score(match_id: int, db: Session = Depends(get_db)):

    match = db.query(models.Match).filter(
        models.Match.id == match_id
    ).first()

    if not match:
        raise HTTPException(404, "Match not found")

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

    last_over = [
        "W" if b.is_wicket else str(b.runs or 0)
        for b in balls[-6:]
    ]

    run_rate = round(total_runs / (legal_balls / 6), 2) if legal_balls else 0

    return {
        "score": score,
        "overs": overs,

        # ✅ FIX: DO NOT override note
        "status": match.note or "Live",

        "last_over": last_over,
        "batsmen": [],
        "bowler": {},
        "extras": 0,
        "run_rate": run_rate
    }


# =========================
# ADD BALL
# =========================
@router.post("/{match_id}/add_ball")
def add_ball(match_id: int, runs: int = 0, wicket: bool = False,
             extra_type: str = None, extra_runs: int = 0,
             db: Session = Depends(get_db)):

    last_ball = db.query(models.Ball).filter(
        models.Ball.match_id == match_id
    ).order_by(models.Ball.id.desc()).first()

    over, ball = 0, 1

    if last_ball:
        over = last_ball.over
        ball = last_ball.ball

        if extra_type not in ["wide", "no_ball"]:
            ball += 1
            if ball > 6:
                over += 1
                ball = 1

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

    db.add(new_ball)
    db.commit()

    return {"message": "Ball added"}


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

@router.post("/{match_id}/result")
def update_result(
        match_id: int,
        winner: str,
        runs_scored: int,
        overs: float,
        db: Session = Depends(get_db)
):
    match = db.query(TournamentMatch).get(match_id)
    match.winner = winner

    # update points
    teams = [match.team_a, match.team_b]

    for team in teams:
        p = db.query(TournamentPoints).filter_by(
            tournament_id=match.tournament_id,
            team_name=team
        ).first()

        p.played += 1

        if team == winner:
            p.wins += 1
            p.points += 2
            p.runs_scored += runs_scored
            p.overs_faced += overs
        else:
            p.losses += 1
            p.runs_conceded += runs_scored
            p.overs_bowled += overs

    db.commit()

    return {"message": "Result updated"}

@router.post("/add_player_to_team")
def add_player_to_team(
        team_id: int,
        player_id: int,
        db: Session = Depends(get_db)
):
    tp = models.TeamPlayer(
        team_id=team_id,
        player_id=player_id
    )

    db.add(tp)
    db.commit()

    return {"message": "Player added to team"}


@router.post("/{match_id}/set_playing_xi")
def set_playing_xi(
        match_id: int,
        team_id: int,
        player_ids: list[int],
        db: Session = Depends(get_db)
):
    if len(player_ids) != 11:
        raise HTTPException(status_code=400, detail="Must select 11 players")

    # clear existing XI
    db.query(models.PlayingXI).filter(
        models.PlayingXI.match_id == match_id,
        models.PlayingXI.team_id == team_id
    ).delete()

    for pid in player_ids:
        xi = models.PlayingXI(
            match_id=match_id,
            team_id=team_id,
            player_id=pid
        )
        db.add(xi)

    db.commit()

    return {"message": "Playing XI set"}