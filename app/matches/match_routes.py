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


@router.get("/get_matches")
def get_matches(email: str, db: Session = Depends(get_db)):
    player = db.query(models.Player).filter(
        models.Player.email == email
    ).first()

    # 🔥 Get matches (filtered or all)
    if not player or not player.team_id:
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

        # ==============================
        # ✅ LIVE MATCH CALCULATION ONLY
        # ==============================
        if m.status == "live":

            balls = db.query(models.Ball).filter(
                models.Ball.match_id == m.id
            ).all()

            total_runs = sum((b.runs or 0) + (b.extra_runs or 0) for b in balls)
            wickets = sum(1 for b in balls if b.is_wicket)

            legal_balls = sum(
                1 for b in balls if b.extra_type not in ["wide", "no_ball"]
            )

            overs = f"{legal_balls // 6}.{legal_balls % 6}"
            scoreA = f"{total_runs}/{wickets}" if balls else ""

            overs_display = overs

        # ==============================
        # ✅ COMPLETED / UPCOMING
        # ==============================
        else:
            scoreA = f"{m.scoreA} ({m.oversA})" if m.scoreA else ""
            overs_display = m.oversA if m.oversA else None

        # ==============================
        # ✅ SCORE B (COMMON)
        # ==============================
        scoreB = f"{m.scoreB} ({m.oversB})" if m.scoreB else ""

        # ==============================
        # ✅ NOTE FIX (IMPORTANT)
        # ==============================
        if m.status == "completed":
            note = m.note or ""
        elif m.current_innings == 2:
            note = m.note or ""
        elif m.status == "live":
            note = f"{m.teamA.name} batting"
        else:
            note = m.note or ""

        # ==============================
        # ✅ FINAL RESPONSE
        # ==============================
        result.append({
            "id": m.id,
            "teamA": m.teamA.name if m.teamA else "",
            "teamB": m.teamB.name if m.teamB else "",

            "scoreA": scoreA,
            "scoreB": scoreB,

            "overs": overs_display,
            "status": m.status,
            "note": note
        })

    return result


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
# LIVE SCORE
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

    # ✅ GET ACTIVE BATSMEN
    batsmen = db.query(models.Batsman).filter(
        models.Batsman.match_id == match_id,
        models.Batsman.is_out == False
    ).all()

    # ✅ FIXED LOOP (INSIDE APPEND)
    batsmen_data = []
    for b in batsmen:
        sr = (b.runs / b.balls * 100) if b.balls > 0 else 0

        batsmen_data.append({
            "name": b.name,
            "runs": b.runs,
            "balls": b.balls,
            "fours": b.fours,
            "sixes": b.sixes,
            "sr": round(sr, 1),
            "is_striker": b.is_striker
        })

    # ✅ BOWLER (TEMP BASIC)
    bowler_data = {
        "name": "Current Bowler",
        "overs": overs,
        "runs": total_runs,
        "wickets": wickets,
        "eco": run_rate
    }

    return {
        "score": score,
        "overs": overs,
        "status": match.note or "Live",
        "last_over": last_over,
        "batsmen": batsmen_data,
        "bowler": bowler_data,
        "extras": 0,
        "run_rate": run_rate
    }

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
#     match = db.query(models.Match).filter(
#         models.Match.id == match_id
#     ).first()
#
#     if not match:
#         raise HTTPException(404, "Match not found")
#
#     # =========================
#     # GET LAST BALL
#     # =========================
#     last_ball = db.query(models.Ball).filter(
#         models.Ball.match_id == match_id
#     ).order_by(models.Ball.id.desc()).first()
#
#     over, ball = 0, 1
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
#     # =========================
#     # CREATE BALL
#     # =========================
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
#     db.add(new_ball)
#     db.commit()
#
#     # =========================
#     # 🔥 RE-CALCULATE MATCH STATE
#     # =========================
#     balls = db.query(models.Ball).filter(
#         models.Ball.match_id == match_id
#     ).all()
#
#     total_runs = sum((b.runs or 0) + (b.extra_runs or 0) for b in balls)
#     wickets = sum(1 for b in balls if b.is_wicket)
#
#     legal_balls = sum(
#         1 for b in balls if b.extra_type not in ["wide", "no_ball"]
#     )
#
#     overs = f"{legal_balls // 6}.{legal_balls % 6}"
#
#     # =========================
#     # 🔥 UPDATE CHASE (IMPORTANT)
#     # =========================
#     if match.current_innings == 2:
#
#         # get first innings score
#         first_score = match.scoreB or match.scoreA
#
#         if first_score:
#             try:
#                 target = int(first_score.split("/")[0]) + 1
#             except:
#                 target = 0
#
#             runs_needed = target - total_runs
#             balls_left = (match.total_overs * 6) - legal_balls
#
#             if runs_needed <= 0:
#                 match.note = f"{match.teamA.name} won the match"
#                 match.status = "completed"
#
#             elif balls_left <= 0:
#                 match.note = f"{match.teamB.name} won the match"
#                 match.status = "completed"
#
#             else:
#                 match.note = f"{match.teamA.name} need {runs_needed} runs in {balls_left} balls"
#
#     else:
#         # first innings → simple status
#         match.note = f"{match.teamA.name} batting"
#
#     db.commit()
#
#     # =========================
#     # RESPONSE
#     # =========================
#     return {
#         "message": "Ball added",
#         "data": {
#             "score": f"{total_runs}/{wickets}",
#             "overs": overs,
#             "runs_last_ball": runs + extra_runs,
#             "is_wicket": wicket
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

@router.post("/{match_id}/add_ball")
def add_ball(
    match_id: int,
    runs: int = 0,
    wicket: bool = False,
    extra_type: str = None,
    extra_runs: int = 0,
    db: Session = Depends(get_db)
):
    match = db.query(models.Match).filter(
        models.Match.id == match_id
    ).first()

    if not match:
        raise HTTPException(404, "Match not found")

    # =========================
    # 🧠 OVER + BALL LOGIC (RESTORED)
    # =========================
    last_ball = db.query(models.Ball).filter(
        models.Ball.match_id == match_id
    ).order_by(models.Ball.id.desc()).first()

    over, ball_num = 0, 1

    if last_ball:
        over = last_ball.over
        ball_num = last_ball.ball

        if extra_type not in ["wide", "no_ball"]:
            ball_num += 1
            if ball_num > 6:
                over += 1
                ball_num = 1

    # =========================
    # 🧑‍🤝‍🧑 GET BATSMEN
    # =========================
    batsmen = db.query(models.Batsman).filter(
        models.Batsman.match_id == match_id,
        models.Batsman.is_out == False
    ).all()

    # ensure 2 batsmen
    while len(batsmen) < 2:
        new = models.Batsman(
            match_id=match_id,
            name=f"Player {len(batsmen)+1}",
            is_striker=(len(batsmen) == 0)
        )
        db.add(new)
        db.commit()
        batsmen.append(new)

    striker = next((b for b in batsmen if b.is_striker), None)
    non_striker = next((b for b in batsmen if not b.is_striker), None)

    # =========================
    # 🎯 CREATE BALL (FIXED)
    # =========================
    new_ball = models.Ball(
        match_id=match_id,
        over=over,
        ball=ball_num,
        runs=runs,
        extra_type=extra_type,
        extra_runs=extra_runs,
        is_wicket=wicket,
        created_at=datetime.utcnow()
    )
    db.add(new_ball)

    # =========================
    # 📊 UPDATE BATSMAN
    # =========================
    if striker:
        if extra_type not in ["wide", "no_ball"]:
            striker.balls += 1

        striker.runs += runs

        if runs == 4:
            striker.fours += 1
        elif runs == 6:
            striker.sixes += 1

    # =========================
    # 💀 WICKET
    # =========================
    if wicket and striker:
        striker.is_out = True
        striker.is_striker = False

        new_batsman = models.Batsman(
            match_id=match_id,
            name="New Batsman",
            is_striker=True
        )
        db.add(new_batsman)

    # =========================
    # 🔄 STRIKE ROTATION
    # =========================
    elif runs % 2 == 1 and striker and non_striker:
        striker.is_striker = False
        non_striker.is_striker = True

    # =========================
    # 🔁 OVER END SWAP
    # =========================
    if ball_num == 6 and striker and non_striker:
        striker.is_striker = not striker.is_striker
        non_striker.is_striker = not non_striker.is_striker

    db.commit()

    return {"message": "Ball added"}

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
