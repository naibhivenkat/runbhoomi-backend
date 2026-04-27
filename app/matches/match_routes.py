from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_

from app.auth.deps import get_current_user_id
from app.database import models
from app.database.db import get_db
from app.database.models import TournamentMatch
from app.utls.permissions import require_admin

router = APIRouter(prefix="/matches")

class AddPlayerRequest(BaseModel):
    team_id: str
    player_id: str

class QuickAddPlayerRequest(BaseModel):
    name: str
    phone: str | None = None


@router.post("/create_match")
def create_match(
        tournament_id: str,
        team_a_id: str,
        team_b_id: str,
        overs: int = 20,
        db: Session = Depends(get_db),
        user_id: str = Depends(get_current_user_id)
):
    require_admin(db, user_id, tournament_id)

    match = models.Match(
        team_a_id=team_a_id,
        team_b_id=team_b_id,
        total_overs=overs,
        status="created",
        admin_id=user_id,
        tournament_id=tournament_id
    )

    db.add(match)
    db.commit()
    db.refresh(match)

    return {"match_id": match.id, "message": "Match created"}


@router.get("/get_matches")
def get_matches(email: str, db: Session = Depends(get_db)):
    player = db.query(models.Player).filter(models.Player.email == email).first()

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
        if m.status == "live":
            balls = db.query(models.Ball).filter(models.Ball.match_id == m.id).all()
            total_runs = sum((b.runs or 0) + (b.extra_runs or 0) for b in balls)
            wickets = sum(1 for b in balls if b.is_wicket)
            legal_balls = sum(1 for b in balls if b.extra_type not in ["wide", "no_ball"])
            overs = f"{legal_balls // 6}.{legal_balls % 6}"
            scoreA = f"{total_runs}/{wickets}" if balls else ""
            overs_display = overs
        else:
            scoreA = f"{m.scoreA} ({m.oversA})" if m.scoreA else ""
            overs_display = m.oversA if m.oversA else None

        scoreB = f"{m.scoreB} ({m.oversB})" if m.scoreB else ""

        if m.status == "completed": note = m.note or ""
        elif m.current_innings == 2: note = m.note or ""
        elif m.status == "live": note = f"{m.teamA.name} batting" if m.teamA else "Live"
        else: note = m.note or ""

        tm = db.query(models.TournamentMatch).filter(models.TournamentMatch.match_id == m.id).first()

        result.append({
            "id": m.id,
            "teamA": m.teamA.name if m.teamA else "",
            "teamB": m.teamB.name if m.teamB else "",
            "teamA_id": m.team_a_id,
            "teamB_id": m.team_b_id,
            "tournament_id": tm.tournament_id if tm else None,
            "is_admin": m.admin_id == player.id if player else False,
            "scoreA": scoreA,
            "scoreB": scoreB,
            "overs": overs_display,
            "status": m.status,
            "note": note,
        })

    return result


@router.get("/{match_id}")
def get_match_detail(match_id: str, db: Session = Depends(get_db)):
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


@router.post("/add_player_to_team")
def add_player_to_team(data: AddPlayerRequest, db: Session = Depends(get_db)):
    existing = db.query(models.TeamPlayer).filter(
        models.TeamPlayer.team_id == data.team_id,
        models.TeamPlayer.player_id == data.player_id
    ).first()

    if existing:
        return {"message": "Player already in team"}

    tp = models.TeamPlayer(team_id=data.team_id, player_id=data.player_id)
    db.add(tp)
    db.commit()
    return {"message": "Player added"}


@router.post("/{match_id}/set_playing_xi")
def set_playing_xi(
        match_id: str,
        team_id: str,
        player_ids: list[str],
        db: Session = Depends(get_db)
):
    if len(player_ids) != 11:
        raise HTTPException(status_code=400, detail="Must select 11 players")

    db.query(models.PlayingXI).filter(
        models.PlayingXI.match_id == match_id,
        models.PlayingXI.team_id == team_id
    ).delete()

    for pid in player_ids:
        xi = models.PlayingXI(match_id=match_id, team_id=team_id, player_id=pid)
        db.add(xi)

    db.commit()
    return {"message": "Playing XI set"}


@router.get("/teams/{team_id}/players")
def get_team_players(team_id: str, db: Session = Depends(get_db)):
    team_players = db.query(models.TeamPlayer).filter(models.TeamPlayer.team_id == team_id).all()
    result = []
    for tp in team_players:
        player = db.query(models.Player).get(tp.player_id)
        if player:
            result.append({"id": player.id, "name": player.name})
    return result


@router.get("/players/search")
def search_players(q: str, team_id: str, db: Session = Depends(get_db)):
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
    if data.phone:
        existing = db.query(models.Player).filter(models.Player.phone == data.phone).first()
        if existing:
            return {"id": existing.id, "name": existing.name}

    player = models.Player(
        name=data.name,
        phone=data.phone,
        email=None,
        password_hash=None
    )
    db.add(player)
    db.commit()
    db.refresh(player)

    return {"id": player.id, "name": player.name}


@router.get("/my-cricket")
def get_my_cricket(
        db: Session = Depends(get_db),
        user_id: str = Depends(get_current_user_id)
):
    user = db.query(models.Player).filter_by(id=user_id).first() # Fixed User to models.Player
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "profile": {
            "name": user.name,
            "role": "All-rounder",
            "matches": 0, "runs": 0, "wickets": 0, "avg": 0, "strike": 0
        },
        "matches": []
    }


@router.get("/tournament/{tournament_id}")
def get_matches_by_tournament(tournament_id: str, db: Session = Depends(get_db)):
    matches = db.query(TournamentMatch).filter_by(tournament_id=tournament_id).all()
    return [
        {
            "team_a": m.team_a, "team_b": m.team_b,
            "team_a_id": m.team_a_id, "team_b_id": m.team_b_id,
            "group": m.group_id, "date": m.match_date,
            "result": f"{m.winner} won" if m.winner else None
        } for m in matches
    ]


# from fastapi import APIRouter, Depends, HTTPException
# from pydantic import BaseModel
# from sqlalchemy.orm import Session, joinedload
#
# from app.auth.deps import get_current_user_id
# from app.database import models
# from app.database.db import get_db
# from app.database.models import TournamentPoints, TournamentMatch
# from app.utls.match_model import BallInput
# from app.utls.permissions import require_admin
#
# router = APIRouter(prefix="/matches")
#
#
# class AddPlayerRequest(BaseModel):
#     team_id: int
#     player_id: int
#
#
# class QuickAddPlayerRequest(BaseModel):
#     name: str
#     phone: str | None = None
#
#
# # =========================
# # CREATE MATCH
# # =========================
#
#
# @router.post("/create_match")
# def create_match(
#         tournament_id: int,
#         team_a_id: int,
#         team_b_id: int,
#         overs: int = 20,
#         db: Session = Depends(get_db),
#         user_id: int = Depends(get_current_user_id)
# ):
#     # 🔐 ADMIN CHECK
#     require_admin(db, user_id, tournament_id)
#
#     match = models.Match(
#         team_a_id=team_a_id,
#         team_b_id=team_b_id,
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
# # =========================
# # START MATCH
# # =========================
#
#
# @router.post("/{match_id}/start_match")
# def start_match(
#     match_id: int,
#     striker_id: int,
#     non_striker_id: int,
#     db: Session = Depends(get_db),
#     user_id: int = Depends(get_current_user_id)
# ):
#     match = db.query(models.Match).get(match_id)
#
#     if match.admin_id != user_id:
#         raise HTTPException(403, "Not allowed")
#
#     # 🔥 CLEAN OLD
#     db.query(models.Batsman).filter(
#         models.Batsman.match_id == match_id
#     ).delete()
#
#     db.query(models.Ball).filter(
#         models.Ball.match_id == match_id
#     ).delete()
#
#     striker = db.query(models.Player).get(striker_id)
#     non_striker = db.query(models.Player).get(non_striker_id)
#
#     db.add(models.Batsman(
#         match_id=match_id,
#         player_id=striker.id,
#         name=striker.name,
#         is_striker=True
#     ))
#
#     db.add(models.Batsman(
#         match_id=match_id,
#         player_id=non_striker.id,
#         name=non_striker.name,
#         is_striker=False
#     ))
#
#     match.status = "live"
#
#     db.commit()
#
#     return {"message": "Match started"}
#
#
#
# @router.get("/get_matches")
# def get_matches(email: str, db: Session = Depends(get_db)):
#     player = db.query(models.Player).filter(
#         models.Player.email == email
#     ).first()
#
#     if not player or not player.team_id:
#         matches = db.query(models.Match).options(
#             joinedload(models.Match.teamA),
#             joinedload(models.Match.teamB)
#         ).all()
#     else:
#         matches = db.query(models.Match).options(
#             joinedload(models.Match.teamA),
#             joinedload(models.Match.teamB)
#         ).filter(
#             (models.Match.team_a_id == player.team_id) |
#             (models.Match.team_b_id == player.team_id)
#         ).all()
#
#     result = []
#
#     for m in matches:
#
#         # ✅ LIVE
#         if m.status == "live":
#             balls = db.query(models.Ball).filter(
#                 models.Ball.match_id == m.id
#             ).all()
#
#             total_runs = sum((b.runs or 0) + (b.extra_runs or 0) for b in balls)
#             wickets = sum(1 for b in balls if b.is_wicket)
#
#             legal_balls = sum(
#                 1 for b in balls if b.extra_type not in ["wide", "no_ball"]
#             )
#
#             overs = f"{legal_balls // 6}.{legal_balls % 6}"
#             scoreA = f"{total_runs}/{wickets}" if balls else ""
#             overs_display = overs
#
#         else:
#             scoreA = f"{m.scoreA} ({m.oversA})" if m.scoreA else ""
#             overs_display = m.oversA if m.oversA else None
#
#         scoreB = f"{m.scoreB} ({m.oversB})" if m.scoreB else ""
#
#         # ✅ NOTE
#         if m.status == "completed":
#             note = m.note or ""
#         elif m.current_innings == 2:
#             note = m.note or ""
#         elif m.status == "live":
#             note = f"{m.teamA.name} batting"
#         else:
#             note = m.note or ""
#
#         # ✅ OPTIONAL tournament mapping
#         tm = db.query(models.TournamentMatch).filter(
#             models.TournamentMatch.match_id == m.id
#         ).first()
#
#         result.append({
#             "id": m.id,
#             "teamA": m.teamA.name if m.teamA else "",
#             "teamB": m.teamB.name if m.teamB else "",
#
#             "teamA_id": m.team_a_id,
#             "teamB_id": m.team_b_id,
#
#             # ✅ SAFE
#             "tournament_id": tm.tournament_id if tm else None,
#
#             # ✅ CRITICAL FOR FRONTEND
#             "is_admin": m.admin_id == player.id if player else False,
#
#             "scoreA": scoreA,
#             "scoreB": scoreB,
#             "overs": overs_display,
#             "status": m.status,
#             "note": note,
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
#         raise HTTPException(404, "Match not found")
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
# # =========================
# # LIVE SCORE
# # =========================
#
#
# @router.get("/{match_id}/live")
# def get_live_score(match_id: int, db: Session = Depends(get_db)):
#     balls = db.query(models.Ball).filter(
#         models.Ball.match_id == match_id
#     ).order_by(models.Ball.id.asc()).all()
#
#     total_runs = sum((b.runs or 0) + (b.extra_runs or 0) for b in balls)
#     wickets = sum(1 for b in balls if b.is_wicket)
#
#     legal_balls = sum(1 for b in balls if b.is_legal_ball)
#
#     overs = f"{legal_balls // 6}.{legal_balls % 6}"
#     score = f"{total_runs}/{wickets}"
#
#     # =========================
#     # LAST OVER (FIXED 🔥)
#     # =========================
#     last_over = []
#     for b in balls[-6:]:
#         if b.is_wicket:
#             last_over.append("W")
#         elif b.extra_type == "wide":
#             last_over.append("WD")
#         elif b.extra_type == "no_ball":
#             last_over.append("NB")
#         else:
#             last_over.append(str(b.runs or 0))
#
#     # =========================
#     # BATSMEN
#     # =========================
#     batsmen = db.query(models.Batsman).filter(
#         models.Batsman.match_id == match_id,
#         models.Batsman.is_out == False
#     ).all()
#
#     batsmen_data = []
#     for b in batsmen:
#         batsmen_data.append({
#             "name": b.name,
#             "runs": b.runs,
#             "balls": b.balls,
#             "is_striker": b.is_striker
#         })
#
#     # =========================
#     # EXTRAS
#     # =========================
#     total_extras = sum(b.extra_runs for b in balls)
#
#     return {
#         "score": score,
#         "overs": overs,
#         "batsmen": batsmen_data,
#         "last_over": last_over,
#         "extras": total_extras
#     }
#
#
#
# @router.post("/{match_id}/add_ball")
# def add_ball(
#     match_id: int,
#     payload: BallInput,
#     db: Session = Depends(get_db),
#     user_id: int = Depends(get_current_user_id)
# ):
#     match = db.query(models.Match).get(match_id)
#
#     if not match:
#         raise HTTPException(404, "Match not found")
#
#     if match.admin_id != user_id:
#         raise HTTPException(403, "Not allowed")
#
#     runs = payload.runs or 0
#     wicket = payload.wicket
#     extra_type = payload.extra_type
#     next_batsman_id = payload.next_batsman_id
#
#     # =========================
#     # EXTRA HANDLING (FIXED 🔥)
#     # =========================
#     is_extra = extra_type in ["wide", "no_ball"]
#
#     # Force 1 run for extras
#     extra_runs = 1 if is_extra else 0
#
#     # =========================
#     # LAST BALL
#     # =========================
#     last_ball = db.query(models.Ball).filter(
#         models.Ball.match_id == match_id
#     ).order_by(models.Ball.id.desc()).first()
#
#     over, ball_num = 0, 1
#
#     if last_ball:
#         over = last_ball.over
#         ball_num = last_ball.ball
#
#         if not is_extra:
#             ball_num += 1
#             if ball_num > 6:
#                 over += 1
#                 ball_num = 1
#
#     # =========================
#     # BATSMEN
#     # =========================
#     batsmen = db.query(models.Batsman).filter(
#         models.Batsman.match_id == match_id,
#         models.Batsman.is_out == False
#     ).all()
#
#     if len(batsmen) < 2:
#         raise HTTPException(400, "Need 2 batsmen")
#
#     striker = next(b for b in batsmen if b.is_striker)
#     non_striker = next(b for b in batsmen if not b.is_striker)
#
#     # =========================
#     # SAVE BALL
#     # =========================
#     new_ball = models.Ball(
#         match_id=match_id,
#         innings=match.current_innings,
#         over=over,
#         ball=ball_num,
#
#         batsman_id=striker.player_id,
#         non_striker_id=non_striker.player_id,
#
#         runs=runs,
#         extra_type=extra_type,
#         extra_runs=extra_runs,
#
#         is_wicket=wicket,
#         player_out_id=striker.player_id if wicket else None,
#
#         is_legal_ball=not is_extra
#     )
#
#     db.add(new_ball)
#
#     # =========================
#     # UPDATE BATSMAN STATS
#     # =========================
#     # Ball faced only for legal delivery
#     if not is_extra:
#         striker.balls += 1
#
#     # Runs always add (even on no-ball)
#     striker.runs += runs
#
#     if runs == 4:
#         striker.fours += 1
#     elif runs == 6:
#         striker.sixes += 1
#
#     # =========================
#     # WICKET
#     # =========================
#     if wicket:
#         striker.is_out = True
#         striker.is_striker = False
#
#         if not next_batsman_id:
#             db.commit()
#             return {"need_next_batsman": True}
#
#         player = db.query(models.Player).get(next_batsman_id)
#
#         new_batsman = models.Batsman(
#             match_id=match_id,
#             player_id=player.id,
#             name=player.name,
#             is_striker=True
#         )
#         db.add(new_batsman)
#
#     else:
#         # 🔥 STRIKE ROTATION (ONLY ON LEGAL BALLS)
#         if not is_extra and runs % 2 == 1:
#             striker.is_striker = False
#             non_striker.is_striker = True
#
#     # =========================
#     # OVER COMPLETE (FIXED)
#     # =========================
#     if not is_extra and ball_num == 6:
#         striker.is_striker = not striker.is_striker
#         non_striker.is_striker = not non_striker.is_striker
#
#     db.commit()
#
#     return {
#         "message": "Ball added",
#         "runs_added": runs + extra_runs,
#         "is_extra": is_extra
#     }
#
#
# @router.post("/{match_id}/reset")
# def reset_match(match_id: int, db: Session = Depends(get_db)):
#     db.query(models.Ball).filter(
#         models.Ball.match_id == match_id
#     ).delete()
#
#     db.query(models.Batsman).filter(
#         models.Batsman.match_id == match_id
#     ).delete()
#
#     db.commit()
#
#     return {"message": "Match reset"}
#
# def update_points(
#         db,
#         tournament_id,
#         team_name,
#         runs_scored,
#         overs_faced,
#         runs_conceded,
#         overs_bowled,
#         is_winner
# ):
#     p = db.query(TournamentPoints).filter_by(
#         tournament_id=tournament_id,
#         team_name=team_name
#     ).first()
#
#     if not p:
#         return
#
#     p.played += 1
#     p.runs_scored += runs_scored
#     p.overs_faced += overs_faced
#     p.runs_conceded += runs_conceded
#     p.overs_bowled += overs_bowled
#
#     if is_winner:
#         p.wins += 1
#         p.points += 2
#     else:
#         p.losses += 1
#
#
# @router.post("/{match_id}/result")
# def update_result(
#         match_id: int,
#         team_a_runs: int,
#         team_a_overs: float,
#         team_b_runs: int,
#         team_b_overs: float,
#         winner: str,
#         db: Session = Depends(get_db)
# ):
#     match = db.query(TournamentMatch).get(match_id)
#
#     if match.winner:
#         return {"message": "Result already submitted"}
#
#     match.winner = winner
#
#     team_a = match.team_a
#     team_b = match.team_b
#
#     # 🔥 Use reusable function
#     update_points(
#         db,
#         match.tournament_id,
#         team_a,
#         team_a_runs,
#         team_a_overs,
#         team_b_runs,
#         team_b_overs,
#         is_winner=(winner == team_a)
#     )
#
#     update_points(
#         db,
#         match.tournament_id,
#         team_b,
#         team_b_runs,
#         team_b_overs,
#         team_a_runs,
#         team_a_overs,
#         is_winner=(winner == team_b)
#     )
#
#     db.commit()
#
#     return {"message": "Result updated successfully"}
#
#
# @router.post("/add_player_to_team")
# def add_player_to_team(data: AddPlayerRequest, db: Session = Depends(get_db)):
#     existing = db.query(models.TeamPlayer).filter(
#         models.TeamPlayer.team_id == data.team_id,
#         models.TeamPlayer.player_id == data.player_id
#     ).first()
#
#     if existing:
#         return {"message": "Player already in team"}
#
#     tp = models.TeamPlayer(
#         team_id=data.team_id,
#         player_id=data.player_id
#     )
#
#     db.add(tp)
#     db.commit()
#
#     return {"message": "Player added"}
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
# @router.get("/teams/{team_id}/players")
# def get_team_players(team_id: int, db: Session = Depends(get_db)):
#     team_players = db.query(models.TeamPlayer).filter(
#         models.TeamPlayer.team_id == team_id
#     ).all()
#
#     result = []
#
#     for tp in team_players:
#         player = db.query(models.Player).get(tp.player_id)
#
#         if player:
#             result.append({
#                 "id": player.id,
#                 "name": player.name
#             })
#
#     return result
#
#
# from sqlalchemy import or_
#
#
# @router.get("/players/search")
# def search_players(q: str, team_id: int, db: Session = Depends(get_db)):
#     players = db.query(models.Player).filter(
#         or_(
#             models.Player.name.ilike(f"%{q}%"),
#             models.Player.phone.ilike(f"%{q}%"),
#             models.Player.email.ilike(f"%{q}%"),
#         )
#     ).all()
#
#     result = []
#
#     for p in players:
#         already = db.query(models.TeamPlayer).filter(
#             models.TeamPlayer.team_id == team_id,
#             models.TeamPlayer.player_id == p.id
#         ).first()
#
#         result.append({
#             "id": p.id,
#             "name": p.name,
#             "phone": p.phone,
#             "email": p.email,
#             "already_added": True if already else False
#         })
#
#     return result
#
#
# @router.post("/players/quick_add")
# def quick_add_player(data: QuickAddPlayerRequest, db: Session = Depends(get_db)):
#     # 1. If phone exists → return existing player
#     if data.phone:
#         existing = db.query(models.Player).filter(
#             models.Player.phone == data.phone
#         ).first()
#
#         if existing:
#             return {"id": existing.id, "name": existing.name}
#
#     # 2. Create new quick player
#     player = models.Player(
#         name=data.name,
#         phone=data.phone,
#         email=None,  # ❗ no fake email
#         password_hash=None  # ❗ no password
#     )
#
#     db.add(player)
#     db.commit()
#     db.refresh(player)
#
#     return {"id": player.id, "name": player.name}
#
#
# @router.get("/my-cricket")
# def get_my_cricket(
#         db: Session = Depends(get_db),
#         user_id: int = Depends(get_current_user_id)
# ):
#     # ✅ get user using ID from token
#     user = db.query(User).filter_by(id=user_id).first()
#
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")
#
#     # 🔥 TEMP (replace with real stats later)
#     return {
#         "profile": {
#             "name": user.name,
#             "role": "All-rounder",
#             "matches": 0,
#             "runs": 0,
#             "wickets": 0,
#             "avg": 0,
#             "strike": 0
#         },
#         "matches": []
#     }
#
#
# @router.get("/tournament/{tournament_id}")
# def get_matches_by_tournament(tournament_id: int, db: Session = Depends(get_db)):
#     matches = db.query(TournamentMatch).filter_by(
#         tournament_id=tournament_id
#     ).all()
#
#     return [
#         {
#             "team_a": m.team_a,
#             "team_b": m.team_b,
#
#             "team_a_id": m.team_a_id,
#             "team_b_id": m.team_b_id,
#
#             "group": m.group_id,
#
#             "date": m.match_date,
#
#             "result": (
#                 f"{m.winner} won"
#                 if m.winner else None
#             )
#         }
#         for m in matches
#     ]
#
#
#
# @router.post("/{match_id}/next_batsman")
# def select_next_batsman(
#     match_id: int,
#     player_id: int,
#     db: Session = Depends(get_db),
#     user_id: int = Depends(get_current_user_id)
# ):
#     match = db.query(models.Match).get(match_id)
#
#     if not match:
#         raise HTTPException(404, "Match not found")
#
#     if match.admin_id != user_id:
#         raise HTTPException(403, "Not allowed")
#
#     # ✅ FIX: use correct batting team
#     batting_team_id = (
#         match.team_a_id if match.current_innings == 1 else match.team_b_id
#     )
#
#     # ✅ FIX: validate using team_players (NOT playing_xi)
#     team_players = db.query(models.TeamPlayer).filter(
#         models.TeamPlayer.team_id == batting_team_id
#     ).all()
#
#     team_player_ids = [tp.player_id for tp in team_players]
#
#     if player_id not in team_player_ids:
#         raise HTTPException(400, "Invalid player")
#
#     # ❌ prevent duplicate batting
#     existing = db.query(models.Batsman).filter(
#         models.Batsman.match_id == match_id,
#         models.Batsman.player_id == player_id
#     ).first()
#
#     if existing:
#         raise HTTPException(400, "Already batted")
#
#     player = db.query(models.Player).get(player_id)
#
#     new_batsman = models.Batsman(
#         match_id=match_id,
#         player_id=player.id,
#         name=player.name,
#         is_striker=True
#     )
#
#     db.add(new_batsman)
#     db.commit()
#
#     return {"message": "New batsman added"}
#
#
# @router.post("/{match_id}/set_bowler")
# def set_bowler(
#     match_id: int,
#     player_id: int,
#     db: Session = Depends(get_db),
#     user_id: int = Depends(get_current_user_id)
# ):
#     match = db.query(models.Match).get(match_id)
#
#     if match.admin_id != user_id:
#         raise HTTPException(403, "Not allowed")
#
#     player = db.query(models.Player).get(player_id)
#
#     if not player:
#         raise HTTPException(404, "Player not found")
#
#     bowler = models.Bowler(
#         match_id=match_id,
#         player_id=player.id,
#         name=player.name,
#         overs="0.0",
#         runs=0,
#         wickets=0,
#         economy=0
#     )
#
#     db.add(bowler)
#     db.commit()
#
#     return {"message": "Bowler set"}
#
#
#
# @router.delete("/{match_id}/undo_ball")
# def undo_ball(
#     match_id: int,
#     db: Session = Depends(get_db),
#     user_id: int = Depends(get_current_user_id)
# ):
#     match = db.query(models.Match).get(match_id)
#
#     if match.admin_id != user_id:
#         raise HTTPException(403, "Not allowed")
#
#     last_ball = db.query(models.Ball).filter(
#         models.Ball.match_id == match_id
#     ).order_by(models.Ball.id.desc()).first()
#
#     if not last_ball:
#         raise HTTPException(400, "No balls to undo")
#
#     db.delete(last_ball)
#     db.commit()
#
#     return {"message": "Last ball removed"}
#
#
#
# @router.post("/{match_id}/next_innings")
# def next_innings(
#     match_id: int,
#     db: Session = Depends(get_db),
#     user_id: int = Depends(get_current_user_id)
# ):
#     match = db.query(models.Match).get(match_id)
#
#     if match.admin_id != user_id:
#         raise HTTPException(403, "Not allowed")
#
#     if match.current_innings == 2:
#         raise HTTPException(400, "Match already finished")
#
#     match.current_innings = 2
#
#     db.commit()
#
#     return {"message": "Second innings started"}
#
# @router.get("/{match_id}/yet_to_bat")
# def get_yet_to_bat(match_id: int, db: Session = Depends(get_db)):
#
#     match = db.query(models.Match).get(match_id)
#
#     if not match:
#         raise HTTPException(404, "Match not found")
#
#     # ✅ get batting team players using JOIN (FIXED)
#     team_players = db.query(
#         models.Player.id,
#         models.Player.name
#     ).join(
#         models.TeamPlayer,
#         models.TeamPlayer.player_id == models.Player.id
#     ).filter(
#         models.TeamPlayer.team_id == match.team_a_id
#     ).all()
#
#     # ✅ already batted
#     batted = db.query(models.Batsman.player_id).filter(
#         models.Batsman.match_id == match_id
#     ).all()
#
#     batted_ids = [b[0] for b in batted]
#
#     # ✅ filter remaining players
#     result = [
#         {
#             "id": p.id,
#             "name": p.name
#         }
#         for p in team_players
#         if p.id not in batted_ids
#     ]
#
#     return {"players": result}
#
# @router.post("/{match_id}/finish")
# def finish_match(
#     match_id: int,
#     db: Session = Depends(get_db),
#     user_id: int = Depends(get_current_user_id)
# ):
#     match = db.query(models.Match).get(match_id)
#
#     if match.admin_id != user_id:
#         raise HTTPException(403, "Not allowed")
#
#     balls = db.query(models.Ball).filter(
#         models.Ball.match_id == match_id
#     ).all()
#
#     total_runs = sum((b.runs or 0) + (b.extra_runs or 0) for b in balls)
#
#     match.status = "completed"
#     match.scoreA = total_runs
#
#     db.commit()
#
#     return {"message": "Match completed"}