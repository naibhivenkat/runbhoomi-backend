from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.database import models
from app.database.db import get_db
from app.database.models import TournamentPoints, TournamentMatch
from app.auth.deps import get_current_user_id
from app.utls.permissions import require_admin

router = APIRouter(prefix="/matches")


class AddPlayerRequest(BaseModel):
    team_id: int
    player_id: int


class QuickAddPlayerRequest(BaseModel):
    name: str
    phone: str | None = None


# =========================
# CREATE MATCH
# =========================


@router.post("/create_match")
def create_match(
        tournament_id: int,
        team_a_id: int,
        team_b_id: int,
        overs: int = 20,
        db: Session = Depends(get_db),
        user_id: int = Depends(get_current_user_id)
):
    # 🔐 ADMIN CHECK
    require_admin(db, user_id, tournament_id)

    match = models.Match(
        team_a_id=team_a_id,
        team_b_id=team_b_id,
        total_overs=overs,
        status="created"
    )

    db.add(match)
    db.commit()
    db.refresh(match)

    return {
        "match_id": match.id,
        "message": "Match created"
    }


# =========================
# START MATCH
# =========================


@router.post("/{match_id}/start_match")
def start_match(
        match_id: int,
        tournament_id: int,
        striker_id: int,
        non_striker_id: int,
        bowler_name: str,
        db: Session = Depends(get_db),
        user_id: int = Depends(get_current_user_id)
):
    # 🔐 ADMIN CHECK
    require_admin(db, user_id, tournament_id)

    match = db.query(models.Match).get(match_id)

    if not match:
        raise HTTPException(404, "Match not found")

    # clear previous
    db.query(models.Batsman).filter(
        models.Batsman.match_id == match_id
    ).delete()

    striker_player = db.query(models.Player).get(striker_id)
    non_striker_player = db.query(models.Player).get(non_striker_id)

    striker = models.Batsman(
        match_id=match_id,
        name=striker_player.name,
        is_striker=True
    )

    non_striker = models.Batsman(
        match_id=match_id,
        name=non_striker_player.name,
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

    # =========================
    # 🧑‍🤝‍🧑 ONLY 2 BATSMEN (STRICT)
    # =========================
    batsmen = db.query(models.Batsman).filter(
        models.Batsman.match_id == match_id,
        models.Batsman.is_out == False
    ).order_by(models.Batsman.id.asc()).limit(2).all()

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

    # =========================
    # 🧠 YET TO BAT (NEW)
    # =========================
    all_players = db.query(models.PlayingXI).filter(
        models.PlayingXI.match_id == match_id
    ).all()

    batted_names = [
        b.name for b in db.query(models.Batsman).filter(
            models.Batsman.match_id == match_id
        ).all()
    ]

    yet_to_bat = [
        p.player.name for p in all_players
        if p.player.name not in batted_names
    ]

    # =========================
    # 🎯 BOWLER
    # =========================
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
        "yet_to_bat": yet_to_bat,  # ✅ NEW
        "bowler": bowler_data,
        "extras": 0,
        "run_rate": run_rate
    }


@router.post("/{match_id}/add_ball")
def add_ball(
        match_id: int,
        tournament_id: int,  # 🔥 REQUIRED
        runs: int = 0,
        wicket: bool = False,
        extra_type: str = None,
        extra_runs: int = 0,
        db: Session = Depends(get_db),
        user_id: int = Depends(get_current_user_id)
):
    # 🔐 BLOCK NON-ADMIN
    require_admin(db, user_id, tournament_id)

    # =========================
    # OVER LOGIC
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
    # GET ACTIVE BATSMEN
    # =========================
    batsmen = db.query(models.Batsman).filter(
        models.Batsman.match_id == match_id,
        models.Batsman.is_out == False
    ).order_by(models.Batsman.id.asc()).all()

    if len(batsmen) > 2:
        for b in batsmen[2:]:
            b.is_out = True
        batsmen = batsmen[:2]

    while len(batsmen) < 2:
        new = models.Batsman(
            match_id=match_id,
            name=f"Player {len(batsmen) + 1}",
            is_striker=(len(batsmen) == 0)
        )
        db.add(new)
        db.commit()
        batsmen.append(new)

    # =========================
    # FIX STRIKER
    # =========================
    strikers = [b for b in batsmen if b.is_striker]

    if len(strikers) != 1:
        batsmen[0].is_striker = True
        for b in batsmen[1:]:
            b.is_striker = False

    striker = next(b for b in batsmen if b.is_striker)
    non_striker = next(b for b in batsmen if not b.is_striker)

    # =========================
    # CREATE BALL
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
    # UPDATE BATSMAN
    # =========================
    if extra_type not in ["wide", "no_ball"]:
        striker.balls += 1

    striker.runs += runs

    if runs == 4:
        striker.fours += 1
    elif runs == 6:
        striker.sixes += 1

    # =========================
    # WICKET
    # =========================
    if wicket:
        striker.is_out = True
        striker.is_striker = False

        new_batsman = models.Batsman(
            match_id=match_id,
            name="Next Player",
            is_striker=True
        )
        db.add(new_batsman)

    else:
        if runs % 2 == 1:
            striker.is_striker = False
            non_striker.is_striker = True

    if ball_num == 6:
        striker.is_striker = not striker.is_striker
        non_striker.is_striker = not non_striker.is_striker

    db.commit()

    # =========================
    # SCORE RESPONSE
    # =========================
    balls = db.query(models.Ball).filter(
        models.Ball.match_id == match_id
    ).all()

    total_runs = sum((b.runs or 0) + (b.extra_runs or 0) for b in balls)
    wickets = sum(1 for b in balls if b.is_wicket)

    legal_balls = sum(
        1 for b in balls if b.extra_type not in ["wide", "no_ball"]
    )

    overs = f"{legal_balls // 6}.{legal_balls % 6}"

    return {
        "message": "Ball added",
        "data": {
            "score": f"{total_runs}/{wickets}",
            "overs": overs,
            "runs_last_ball": runs + extra_runs,
            "is_wicket": wicket
        }
    }


def update_points(
        db,
        tournament_id,
        team_name,
        runs_scored,
        overs_faced,
        runs_conceded,
        overs_bowled,
        is_winner
):
    p = db.query(TournamentPoints).filter_by(
        tournament_id=tournament_id,
        team_name=team_name
    ).first()

    if not p:
        return

    p.played += 1
    p.runs_scored += runs_scored
    p.overs_faced += overs_faced
    p.runs_conceded += runs_conceded
    p.overs_bowled += overs_bowled

    if is_winner:
        p.wins += 1
        p.points += 2
    else:
        p.losses += 1


@router.post("/{match_id}/result")
def update_result(
        match_id: int,
        team_a_runs: int,
        team_a_overs: float,
        team_b_runs: int,
        team_b_overs: float,
        winner: str,
        db: Session = Depends(get_db)
):
    match = db.query(TournamentMatch).get(match_id)

    if match.winner:
        return {"message": "Result already submitted"}

    match.winner = winner

    team_a = match.team_a
    team_b = match.team_b

    # 🔥 Use reusable function
    update_points(
        db,
        match.tournament_id,
        team_a,
        team_a_runs,
        team_a_overs,
        team_b_runs,
        team_b_overs,
        is_winner=(winner == team_a)
    )

    update_points(
        db,
        match.tournament_id,
        team_b,
        team_b_runs,
        team_b_overs,
        team_a_runs,
        team_a_overs,
        is_winner=(winner == team_b)
    )

    db.commit()

    return {"message": "Result updated successfully"}


@router.post("/add_player_to_team")
def add_player_to_team(data: AddPlayerRequest, db: Session = Depends(get_db)):
    existing = db.query(models.TeamPlayer).filter(
        models.TeamPlayer.team_id == data.team_id,
        models.TeamPlayer.player_id == data.player_id
    ).first()

    if existing:
        return {"message": "Player already in team"}

    tp = models.TeamPlayer(
        team_id=data.team_id,
        player_id=data.player_id
    )

    db.add(tp)
    db.commit()

    return {"message": "Player added"}


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


@router.get("/teams/{team_id}/players")
def get_team_players(team_id: int, db: Session = Depends(get_db)):
    team_players = db.query(models.TeamPlayer).filter(
        models.TeamPlayer.team_id == team_id
    ).all()

    result = []

    for tp in team_players:
        player = db.query(models.Player).get(tp.player_id)

        if player:
            result.append({
                "id": player.id,
                "name": player.name
            })

    return result


from sqlalchemy import or_


@router.get("/players/search")
def search_players(q: str, team_id: int, db: Session = Depends(get_db)):
    players = db.query(models.Player).filter(
        or_(
            models.Player.name.ilike(f"%{q}%"),
            models.Player.phone.ilike(f"%{q}%"),
            models.Player.email.ilike(f"%{q}%"),
        )
    ).all()

    result = []

    for p in players:
        already = db.query(models.TeamPlayer).filter(
            models.TeamPlayer.team_id == team_id,
            models.TeamPlayer.player_id == p.id
        ).first()

        result.append({
            "id": p.id,
            "name": p.name,
            "phone": p.phone,
            "email": p.email,
            "already_added": True if already else False
        })

    return result


@router.post("/players/quick_add")
def quick_add_player(data: QuickAddPlayerRequest, db: Session = Depends(get_db)):
    # 1. If phone exists → return existing player
    if data.phone:
        existing = db.query(models.Player).filter(
            models.Player.phone == data.phone
        ).first()

        if existing:
            return {"id": existing.id, "name": existing.name}

    # 2. Create new quick player
    player = models.Player(
        name=data.name,
        phone=data.phone,
        email=None,  # ❗ no fake email
        password_hash=None  # ❗ no password
    )

    db.add(player)
    db.commit()
    db.refresh(player)

    return {"id": player.id, "name": player.name}


@router.get("/my-cricket")
def get_my_cricket(
        db: Session = Depends(get_db),
        user_id: int = Depends(get_current_user_id)
):
    # ✅ get user using ID from token
    user = db.query(User).filter_by(id=user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 🔥 TEMP (replace with real stats later)
    return {
        "profile": {
            "name": user.name,
            "role": "All-rounder",
            "matches": 0,
            "runs": 0,
            "wickets": 0,
            "avg": 0,
            "strike": 0
        },
        "matches": []
    }


@router.get("/tournament/{tournament_id}")
def get_matches_by_tournament(tournament_id: int, db: Session = Depends(get_db)):
    matches = db.query(TournamentMatch).filter_by(
        tournament_id=tournament_id
    ).all()

    return [
        {
            "team_a": m.team_a,
            "team_b": m.team_b,

            "team_a_id": m.team_a_id,
            "team_b_id": m.team_b_id,

            "group": m.group_id,

            "date": m.match_date,

            "result": (
                f"{m.winner} won"
                if m.winner else None
            )
        }
        for m in matches
    ]
