import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_

from app.auth.deps import get_current_user_id
from app.database import models
from app.database.db import get_db
from app.database.models import TournamentMatch, generate_uuid
from app.utls.match_model import BallInput
from app.utls.permissions import require_admin

router = APIRouter(prefix="/matches")


class AddPlayerRequest(BaseModel):
    team_id: str
    player_id: str


class QuickAddPlayerRequest(BaseModel):
    name: str
    phone: str | None = None


class StartMatchRequest(BaseModel):
    striker_id: str
    non_striker_id: str
    bowler_id: str
    toss_winner: str
    toss_decision: str
    max_overs: int


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

        if m.status == "completed":
            note = m.note or ""
        elif m.current_innings == 2:
            note = m.note or ""
        elif m.status == "live":
            note = f"{m.teamA.name} batting" if m.teamA else "Live"
        else:
            note = m.note or ""

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


@router.post("/{match_id}/ball")
def add_ball(
        match_id: str,
        payload: BallInput,
        db: Session = Depends(get_db),
        user_id: str = Depends(get_current_user_id)
):
    # 1. Resolve ID: Check if match_id is actually a Fixture ID
    match = db.query(models.Match).filter(models.Match.id == match_id).first()

    if not match:
        # Try to find match via fixture link
        fixture = db.query(models.TournamentMatch).filter(models.TournamentMatch.id == match_id).first()
        if fixture and fixture.match_id:
            match = db.query(models.Match).filter(models.Match.id == fixture.match_id).first()

    if not match:
        logging.error(f"❌ MATCH NOT FOUND: {match_id}")
        raise HTTPException(404, "Match not found")

    # Use the REAL match internal ID for the rest of the function
    match_id = match.id

    # 2. Permission Check (Fixes your 403 error)
    # Using your require_admin utility to check Tournament-level permissions
    require_admin(db, user_id, match.tournament_id)

    runs = payload.runs or 0
    wicket = payload.wicket
    extra_type = payload.extra_type
    next_batsman_id = payload.next_batsman_id

    # 3. Extra Handling
    is_extra = extra_type in ["wide", "no_ball"]
    extra_runs = 1 if is_extra else 0

    # 4. Over & Ball Number Logic
    last_ball = db.query(models.Ball).filter(
        models.Ball.match_id == match_id
    ).order_by(models.Ball.id.desc()).first()

    over, ball_num = 0, 1
    if last_ball:
        over = last_ball.over
        ball_num = last_ball.ball
        if not is_extra:
            ball_num += 1
            if ball_num > 6:
                over += 1
                ball_num = 1

    # 5. Batsman Retrieval
    batsmen = db.query(models.Batsman).filter(
        models.Batsman.match_id == match_id,
        models.Batsman.is_out == False
    ).all()

    if len(batsmen) < 2:
        raise HTTPException(400, "Need 2 batsmen on the field")

    striker = next((b for b in batsmen if b.is_striker), None)
    non_striker = next((b for b in batsmen if not b.is_striker), None)

    if not striker or not non_striker:
        raise HTTPException(400, "Could not identify striker/non-striker")

    # 6. Save Ball Record
    # new_ball = models.Ball(
    #     match_id=match_id,
    #     innings=match.current_innings,
    #     over=over,
    #     ball=ball_num,
    #     batsman_id=striker.player_id,
    #     non_striker_id=non_striker.player_id,
    #     runs=runs,
    #     extra_type=extra_type,
    #     extra_runs=extra_runs,
    #     is_wicket=wicket,
    #     player_out_id=striker.player_id if wicket else None,
    #     is_legal_ball=not is_extra
    # )
    new_ball = models.Ball(
        match_id=match_id,
        innings=match.current_innings,
        over=over,
        ball=ball_num,
        batsman_id=striker.player_id,
        non_striker_id=non_striker.player_id,
        bowler_id=payload.current_bowler_id,
        runs=runs,
        extra_type=extra_type,
        extra_runs=extra_runs,
        is_wicket=wicket,
        player_out_id=striker.player_id if wicket else None,
        is_legal_ball=not is_extra
    )
    db.add(new_ball)

    # 7. Update Batsman Stats
    if not is_extra:
        striker.balls += 1

    # Runs on No-Balls count for the batsman; Wides do not
    if extra_type != "wide":
        striker.runs += runs
        if runs == 4:
            striker.fours += 1
        elif runs == 6:
            striker.sixes += 1

    # 8. Wicket Logic
    if wicket:
        striker.is_out = True
        striker.is_striker = False

        if not next_batsman_id:
            db.commit()
            return {"need_next_batsman": True, "message": "Wicket! Provide next batsman."}

        player = db.query(models.Player).filter(
            models.Player.id == next_batsman_id
        ).first()
        new_batsman = models.Batsman(
            match_id=match_id,
            player_id=player.id,
            name=player.name,
            is_striker=True,
            is_out=False
        )
        db.add(new_batsman)
        logging.info(f"Player Name : {player.name}")
    else:
        # Strike Rotation (Odd runs on legal balls)
        if not is_extra and runs % 2 == 1:
            striker.is_striker = False
            non_striker.is_striker = True

    # 9. Over End Strike Rotation
    if not is_extra and ball_num == 6:
        # Note: If strike rotated on the 6th ball, it rotates again here
        striker.is_striker = not striker.is_striker
        non_striker.is_striker = not non_striker.is_striker

    db.commit()

    return {
        "message": "Ball added",
        "runs_added": runs + extra_runs,
        "is_extra": is_extra,
        "over": over,
        "ball": ball_num
    }


@router.get("/teams/{team_id}/players")
def get_team_players(team_id: str, db: Session = Depends(get_db)):
    results = db.query(models.Player, models.TeamPlayer).join(
        models.TeamPlayer, models.Player.id == models.TeamPlayer.player_id
    ).filter(models.TeamPlayer.team_id == team_id).all()

    return [{
        "id": p.id,
        "name": p.name,
        "role": tp.role,
        "player_type": tp.player_type,  # MUST MATCH KEY IN FLUTTER
        "is_captain": tp.is_captain,  # MUST MATCH KEY IN FLUTTER
        "is_vc": tp.is_vc,
        "is_wk": tp.is_wk
    } for p, tp in results]


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
    user = db.query(models.Player).filter_by(id=user_id).first()  # Fixed User to models.Player
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






@router.post("/{fixture_or_match_id}/start_match")
def start_match(
    fixture_or_match_id: str,
    payload: StartMatchRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    # -------------------------------
    # 1. Resolve Fixture or Match
    # -------------------------------
    fixture = db.query(models.TournamentMatch).filter(
        models.TournamentMatch.id == fixture_or_match_id
    ).first()

    match_id = None

    if fixture:
        if fixture.match_id:
            match_id = fixture.match_id
        else:
            new_match = models.Match(
                team_a_id=fixture.team_a_id,
                team_b_id=fixture.team_b_id,
                total_overs=payload.max_overs,
                status="scheduled",
                tournament_id=fixture.tournament_id,
                admin_id=user_id,
            )
            db.add(new_match)
            db.flush()

            match_id = new_match.id
            fixture.match_id = match_id
    else:
        match = db.query(models.Match).filter(
            models.Match.id == fixture_or_match_id
        ).first()

        if not match:
            raise HTTPException(status_code=404, detail="Match or Fixture not found")

        match_id = match.id

    # -------------------------------
    # 2. Load Match + Admin Check
    # -------------------------------
    target_match = db.query(models.Match).get(match_id)
    require_admin(db, user_id, target_match.tournament_id)

    # -------------------------------
    # 3. Resume Logic (🔥 CRITICAL)
    # -------------------------------
    existing_balls = db.query(models.Ball).filter(
        models.Ball.match_id == match_id
    ).count()

    if target_match.status == "live" and existing_balls > 0:
        return {
            "message": "Match already in progress",
            "match_id": match_id,
            "resume": True
        }

    # -------------------------------
    # 4. Reset ONLY if fresh start
    # -------------------------------
    if target_match.status != "live":
        db.query(models.Batsman).filter(
            models.Batsman.match_id == match_id
        ).delete()

        db.query(models.Bowler).filter(
            models.Bowler.match_id == match_id
        ).delete()

        db.query(models.Ball).filter(
            models.Ball.match_id == match_id
        ).delete()

    # -------------------------------
    # 5. Prevent Duplicate Creation
    # -------------------------------
    existing_batsmen = db.query(models.Batsman).filter(
        models.Batsman.match_id == match_id
    ).count()

    existing_bowler = db.query(models.Bowler).filter(
        models.Bowler.match_id == match_id
    ).count()

    # -------------------------------
    # 6. Setup Openers
    # -------------------------------
    if existing_batsmen == 0:
        for p_id, striker_flag in [
            (payload.striker_id, True),
            (payload.non_striker_id, False)
        ]:
            player = db.query(models.Player).get(p_id)

            if not player:
                raise HTTPException(status_code=400, detail=f"Player {p_id} not found")

            db.add(models.Batsman(
                id=generate_uuid(),
                match_id=match_id,
                player_id=player.id,
                name=player.name,   # 🔥 ALWAYS STORE NAME
                runs=0,
                balls=0,
                fours=0,
                sixes=0,
                is_striker=striker_flag,
                is_out=False
            ))

    # -------------------------------
    # 7. Setup Bowler
    # -------------------------------
    if existing_bowler == 0:
        bowler_p = db.query(models.Player).get(payload.bowler_id)

        if not bowler_p:
            raise HTTPException(status_code=400, detail="Bowler not found")

        db.add(models.Bowler(
            id=generate_uuid(),
            match_id=match_id,
            name=bowler_p.name,
            overs="0.0",
            runs=0,
            wickets=0,
            economy=0.0
        ))
    # -------------------------------
    # 8. Finalize Match
    # -------------------------------
    target_match.status = "live"
    target_match.total_overs = payload.max_overs

    db.commit()

    # -------------------------------
    # 9. Response
    # -------------------------------
    return {
        "message": "Match started successfully",
        "match_id": match_id,
        "resume": False
    }


# TODO :

# @router.post("/{fixture_or_match_id}/start_match")
# def start_match(
#         fixture_or_match_id: str,
#         payload: StartMatchRequest,
#         db: Session = Depends(get_db),
#         user_id: str = Depends(get_current_user_id)
# ):
#     # 1. Try to find if this is a Tournament Fixture first
#     fixture = db.query(models.TournamentMatch).filter(models.TournamentMatch.id == fixture_or_match_id).first()
#
#     match_id = None
#
#     if fixture:
#         # If the fixture already has a match_id, use it.
#         # Otherwise, CREATE a new Match record for this fixture.
#         if fixture.match_id:
#             match_id = fixture.match_id
#         else:
#             new_match = models.Match(
#                 team_a_id=fixture.team_a_id,
#                 team_b_id=fixture.team_b_id,
#                 total_overs=payload.max_overs,
#                 status="live",
#                 tournament_id=fixture.tournament_id,
#                 admin_id=user_id
#             )
#             db.add(new_match)
#             db.flush()  # 🔥 Generates the ID immediately
#             match_id = new_match.id
#             fixture.match_id = match_id  # Link fixture to match
#     else:
#         # If not a fixture, assume it's a direct Match ID
#         match = db.query(models.Match).filter(models.Match.id == fixture_or_match_id).first()
#         if not match:
#             raise HTTPException(404, "Match or Fixture not found")
#         match_id = match.id
#
#     # 2. Permission Check using the resolved match context
#     # (Assuming you fetch the match object to get tournament_id)
#     target_match = db.query(models.Match).get(match_id)
#     require_admin(db, user_id, target_match.tournament_id)
#
#     # 3. Clear existing setup data (Reset for re-starts)
#     db.query(models.Batsman).filter(models.Batsman.match_id == match_id).delete()
#     db.query(models.Ball).filter(models.Ball.match_id == match_id).delete()
#     db.query(models.Bowler).filter(models.Bowler.match_id == match_id).delete()
#
#     # 4. Setup Openers
#     for p_id, striker_flag in [(payload.striker_id, True), (payload.non_striker_id, False)]:
#         player = db.query(models.Player).get(p_id)
#         if player:
#             db.add(models.Batsman(match_id=match_id, player_id=player.id, name=player.name, is_striker=striker_flag,
#                                   is_out=False))
#
#     # 5. Setup Opening Bowler
#     bowler_p = db.query(models.Player).get(payload.bowler_id)
#     if bowler_p:
#         db.add(models.Bowler(id=generate_uuid(), match_id=match_id, name=bowler_p.name, overs="0.0"))
#
#     # 6. Finalize Status
#     target_match.status = "live"
#     target_match.total_overs = payload.max_overs
#
#     db.commit()
#     return {"message": "Match started successfully", "match_id": match_id}



@router.get("/tournament/{tournament_id}")
def get_matches_by_tournament(tournament_id: str, db: Session = Depends(get_db)):
    matches = db.query(TournamentMatch).filter_by(tournament_id=tournament_id).all()
    return [
        {
            "id": m.id,  # Fixture ID
            "match_id": m.match_id,
            "team_a": m.team_a,
            "team_b": m.team_b,
            "team_a_id": m.team_a_id,
            "team_b_id": m.team_b_id,
            "group_id": m.group_id,
            "winner": m.winner,
            "is_live": True if m.match_id else False
        } for m in matches
    ]


@router.get("/{match_id}/live")
def get_live_score(match_id: str, db: Session = Depends(get_db)):
    # =========================
    # BALLS
    # =========================
    balls = db.query(models.Ball).filter(
        models.Ball.match_id == match_id
    ).order_by(models.Ball.id.asc()).all()

    total_runs = sum((b.runs or 0) + (b.extra_runs or 0) for b in balls)
    wickets = sum(1 for b in balls if b.is_wicket)

    legal_balls = sum(1 for b in balls if b.is_legal_ball)

    overs = f"{legal_balls // 6}.{legal_balls % 6}"
    score = f"{total_runs}/{wickets}"

    # =========================
    # LAST OVER
    # =========================
    last_over = []
    for b in balls[-6:]:
        if b.is_wicket:
            last_over.append("W")
        elif b.extra_type == "wide":
            last_over.append("Wd")
        elif b.extra_type == "no_ball":
            last_over.append("Nb")
        else:
            last_over.append(str(b.runs or 0))

    # =========================
    # BATSMEN
    # =========================
    batsmen = db.query(models.Batsman).filter(
        models.Batsman.match_id == match_id,
        models.Batsman.is_out == False
    ).all()

    batsmen_data = [
        {
            "id": b.player_id,
            "name": b.name,
            "runs": b.runs,
            "balls": b.balls,
            "fours": b.fours,
            "sixes": b.sixes,
            "is_striker": b.is_striker
        }
        for b in batsmen
    ]

    # =========================
    # EXTRAS
    # =========================
    total_extras = sum(b.extra_runs for b in balls)

    # =========================
    # ✅ CURRENT BOWLER (FIXED — FROM BALLS)
    # =========================
    bowler_data = None

    # get latest ball
    current_ball = db.query(models.Ball).filter(
        models.Ball.match_id == match_id
    ).order_by(models.Ball.id.desc()).first()

    if current_ball and current_ball.bowler_id:

        bowler_balls = db.query(models.Ball).filter(
            models.Ball.match_id == match_id,
            models.Ball.bowler_id == current_ball.bowler_id
        ).all()

        runs_conceded = sum((b.runs or 0) + (b.extra_runs or 0) for b in bowler_balls)
        wickets_taken = sum(1 for b in bowler_balls if b.is_wicket)
        legal_balls_bowled = sum(1 for b in bowler_balls if b.is_legal_ball)

        bowler_overs = f"{legal_balls_bowled // 6}.{legal_balls_bowled % 6}"

        economy = "0.00"
        if legal_balls_bowled > 0:
            economy = f"{runs_conceded / (legal_balls_bowled / 6):.2f}"

        player = db.query(models.Player).filter(
            models.Player.id == current_ball.bowler_id
        ).first()

        bowler_data = {
            "id": current_ball.bowler_id,
            "name": player.name if player else "Unknown",
            "overs": bowler_overs,
            "runs": runs_conceded,
            "wickets": wickets_taken,
            "economy": economy
        }


    # get match
    match = db.query(models.Match).filter(
        models.Match.id == match_id
    ).first()

    if not match:
        fixture = db.query(models.TournamentMatch).filter(
            models.TournamentMatch.id == match_id
        ).first()

        if fixture and fixture.match_id:
            match = db.query(models.Match).filter(
                models.Match.id == fixture.match_id
            ).first()

    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    # 🔥 IMPORTANT: use resolved match_id
    match_id = match.id
    # =========================
    # FINAL RESPONSE
    # =========================

    return {
        "score": score,
        "overs": overs,
        "target": match.target or 0, 
        "innings": match.current_innings or 1,

        "batsmen": batsmen_data,
        "bowler": bowler_data,
        "last_over": last_over,
        "extras": total_extras
    }


@router.get("/{match_or_fixture_id}/resume")
def resume_match(match_or_fixture_id: str, db: Session = Depends(get_db)):

    # 1️⃣ Try direct match
    match = db.query(models.Match).filter(
        models.Match.id == match_or_fixture_id
    ).first()

    # 2️⃣ If not found → try fixture
    if not match:
        fixture = db.query(models.TournamentMatch).filter(
            models.TournamentMatch.id == match_or_fixture_id
        ).first()

        if fixture and fixture.match_id:
            match = db.query(models.Match).filter(
                models.Match.id == fixture.match_id
            ).first()

    if not match:
        raise HTTPException(404, "Match not found")

    balls = db.query(models.Ball).filter(
        models.Ball.match_id == match.id
    ).order_by(models.Ball.id.asc()).all()

    total_runs = sum((b.runs or 0) + (b.extra_runs or 0) for b in balls)
    wickets = sum(1 for b in balls if b.is_wicket)

    legal_balls = sum(1 for b in balls if b.is_legal_ball)
    overs = f"{legal_balls // 6}.{legal_balls % 6}"

    return {
        "match_id": match.id,
        "status": match.status,
        "score": f"{total_runs}/{wickets}",
        "overs": overs,
        "balls_count": len(balls),
        "has_data": True if balls else False
    }

@router.delete("/{match_id}/ball/last_ball_undo")
def undo_last_ball(
        match_id: str,
        db: Session = Depends(get_db),
        user_id: str = Depends(get_current_user_id)
):
    # 1. Find the last ball bowled in this match
    # We order by timestamp descending to get the most recent one
    last_ball = db.query(models.Ball).filter(
        models.Ball.match_id == match_id
    ).order_by(models.Ball.timestamp.desc()).first()

    if not last_ball:
        raise HTTPException(status_code=404, detail="No balls found to undo")

    try:
        # 2. Delete the ball
        db.delete(last_ball)
        db.commit()

        return {"status": "success", "message": "Last ball deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error during undo: {str(e)}")


@router.post("/{match_id}/match_reset")
def reset_match_scoring(
        match_id: str,
        db: Session = Depends(get_db),
        user_id: str = Depends(get_current_user_id)
):
    # This wipes ALL balls for a match to start fresh
    try:
        db.query(models.Ball).filter(models.Ball.match_id == match_id).delete()

        # Optional: Reset match status or scores in the Match table if you store them there
        match = db.query(models.Match).filter(models.Match.id == match_id).first()
        if match:
            match.is_live = False  # Or whatever your 'reset' logic requires

        db.commit()
        return {"status": "success", "message": "Match scoring reset"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{match_id}/end_innings")
def end_innings(match_id: str, db: Session = Depends(get_db)):
    # 🔥 SAME RESOLVE LOGIC AS /ball
    match = db.query(models.Match).filter(
        models.Match.id == match_id
    ).first()

    if not match:
        fixture = db.query(models.TournamentMatch).filter(
            models.TournamentMatch.id == match_id
        ).first()

        if fixture and fixture.match_id:
            match = db.query(models.Match).filter(
                models.Match.id == fixture.match_id
            ).first()

    if not match:
        raise HTTPException(404, "Match not found")

    # -------------------------
    # CALCULATE FIRST INNINGS SCORE
    # -------------------------
    balls = db.query(models.Ball).filter(
        models.Ball.match_id == match.id,
        models.Ball.innings == match.current_innings
    ).all()

    total_runs = sum((b.runs or 0) + (b.extra_runs or 0) for b in balls)

    # -------------------------
    # UPDATE MATCH
    # -------------------------
    match.target = total_runs + 1
    match.current_innings = 2

    db.commit()

    return {
        "message": "Innings ended",
        "target": match.target
    }


@router.post("/{match_id}/end_match")
def end_match(match_id: str, db: Session = Depends(get_db)):
    # -------------------------------
    # 🔥 RESOLVE MATCH OR FIXTURE ID
    # -------------------------------
    match = db.query(models.Match).filter(
        models.Match.id == match_id
    ).first()

    if not match:
        fixture = db.query(models.TournamentMatch).filter(
            models.TournamentMatch.id == match_id
        ).first()

        if fixture and fixture.match_id:
            match = db.query(models.Match).filter(
                models.Match.id == fixture.match_id
            ).first()

    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    # -------------------------------
    # 🔥 CALCULATE FINAL SCORE
    # -------------------------------
    balls = db.query(models.Ball).filter(
        models.Ball.match_id == match.id
    ).all()

    total_runs = sum((b.runs or 0) + (b.extra_runs or 0) for b in balls)
    wickets = sum(1 for b in balls if b.is_wicket)

    # -------------------------------
    # 🔥 MATCH RESULT LOGIC
    # -------------------------------
    result = "Match tied"

    if match.target:
        if total_runs >= match.target:
            result = "Batting team won"
        else:
            result = "Bowling team won"

    # -------------------------------
    # 🔥 UPDATE MATCH
    # -------------------------------
    match.status = "completed"
    match.final_score = f"{total_runs}/{wickets}"
    match.result = result

    db.commit()

    # -------------------------------
    # RESPONSE
    # -------------------------------
    return {
        "message": "Match completed",
        "final_score": match.final_score,
        "result": result
    }

@router.get("/{match_id}/scorecard")
def get_scorecard(match_id: str, db: Session = Depends(get_db)):
    balls = db.query(models.Ball).filter(
        models.Ball.match_id == match_id
    ).all()

    # -----------------------
    # TEAM SCORE
    # -----------------------
    total_runs = sum((b.runs or 0) + (b.extra_runs or 0) for b in balls)
    wickets = sum(1 for b in balls if b.is_wicket)

    # -----------------------
    # BATSMEN
    # -----------------------
    batsmen = db.query(models.Batsman).filter(
        models.Batsman.match_id == match_id
    ).all()

    batsmen_data = [
        {
            "name": b.name,
            "runs": b.runs,
            "balls": b.balls,
            "fours": b.fours,
            "sixes": b.sixes,
            "strike_rate": round((b.runs / b.balls) * 100, 2) if b.balls > 0 else 0
        }
        for b in batsmen
    ]

    # -----------------------
    # BOWLERS (FROM BALLS 🔥)
    # -----------------------
    bowler_map = {}

    for b in balls:
        if not b.bowler_id:
            continue

        if b.bowler_id not in bowler_map:
            bowler_map[b.bowler_id] = {
                "runs": 0,
                "wickets": 0,
                "balls": 0
            }

        bowler_map[b.bowler_id]["runs"] += (b.runs or 0) + (b.extra_runs or 0)

        if b.is_wicket:
            bowler_map[b.bowler_id]["wickets"] += 1

        if b.is_legal_ball:
            bowler_map[b.bowler_id]["balls"] += 1

    bowlers_data = []

    for bowler_id, stats in bowler_map.items():
        player = db.query(models.Player).filter(
            models.Player.id == bowler_id
        ).first()

        overs = f"{stats['balls']//6}.{stats['balls']%6}"

        economy = 0.0
        if stats["balls"] > 0:
            economy = stats["runs"] / (stats["balls"] / 6)

        bowlers_data.append({
            "name": player.name if player else "Unknown",
            "overs": overs,
            "runs": stats["runs"],
            "wickets": stats["wickets"],
            "economy": round(economy, 2)
        })

    # -----------------------
    # EXTRAS
    # -----------------------
    extras = sum(b.extra_runs for b in balls)

    # -----------------------
    # FINAL RESPONSE
    # -----------------------
    return {
        "score": f"{total_runs}/{wickets}",
        "batsmen": batsmen_data,
        "bowlers": bowlers_data,
        "extras": extras
    }