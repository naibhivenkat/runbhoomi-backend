from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.auth.deps import get_current_user_id
from app.database import models
from app.database.db import get_db
from app.database.models import TournamentPoints, TournamentMatch
from app.utls.match_model import BallInput

router = APIRouter(prefix="/scoring")  # Differentiated prefix


@router.post("/{match_id}/start_match")
def start_match(
        match_id: str,
        striker_id: str,
        non_striker_id: str,
        db: Session = Depends(get_db),
        user_id: str = Depends(get_current_user_id)
):
    match = db.query(models.Match).get(match_id)
    if match.admin_id != user_id:
        raise HTTPException(403, "Not allowed")

    db.query(models.Batsman).filter(models.Batsman.match_id == match_id).delete()
    db.query(models.Ball).filter(models.Ball.match_id == match_id).delete()

    striker = db.query(models.Player).get(striker_id)
    non_striker = db.query(models.Player).get(non_striker_id)

    db.add(models.Batsman(match_id=match_id, player_id=striker.id, name=striker.name, is_striker=True))
    db.add(models.Batsman(match_id=match_id, player_id=non_striker.id, name=non_striker.name, is_striker=False))

    match.status = "live"
    db.commit()
    return {"message": "Match started"}


@router.get("/{match_id}/live")
def get_live_score(match_id: str, db: Session = Depends(get_db)):
    balls = db.query(models.Ball).filter(models.Ball.match_id == match_id).order_by(models.Ball.id.asc()).all()

    total_runs = sum((b.runs or 0) + (b.extra_runs or 0) for b in balls)
    wickets = sum(1 for b in balls if b.is_wicket)
    legal_balls = sum(1 for b in balls if b.is_legal_ball)

    overs = f"{legal_balls // 6}.{legal_balls % 6}"
    score = f"{total_runs}/{wickets}"

    last_over = []
    for b in balls[-6:]:
        if b.is_wicket:
            last_over.append("W")
        elif b.extra_type == "wide":
            last_over.append("WD")
        elif b.extra_type == "no_ball":
            last_over.append("NB")
        else:
            last_over.append(str(b.runs or 0))

    batsmen = db.query(models.Batsman).filter(models.Batsman.match_id == match_id, models.Batsman.is_out == False).all()
    batsmen_data = [{"name": b.name, "runs": b.runs, "balls": b.balls, "is_striker": b.is_striker} for b in batsmen]

    total_extras = sum(b.extra_runs for b in balls)

    return {
        "score": score,
        "overs": overs,
        "batsmen": batsmen_data,
        "last_over": last_over,
        "extras": total_extras
    }


@router.post("/{match_id}/add_ball")
def add_ball(
        match_id: str,
        payload: BallInput,
        db: Session = Depends(get_db),
        user_id: str = Depends(get_current_user_id)
):
    match = db.query(models.Match).get(match_id)
    if not match: raise HTTPException(404, "Match not found")
    if match.admin_id != user_id: raise HTTPException(403, "Not allowed")

    runs = payload.runs or 0
    wicket = payload.wicket
    extra_type = payload.extra_type
    next_batsman_id = payload.next_batsman_id  # Make sure this is a str in BallInput schema

    is_extra = extra_type in ["wide", "no_ball"]
    extra_runs = 1 if is_extra else 0

    last_ball = db.query(models.Ball).filter(models.Ball.match_id == match_id).order_by(models.Ball.id.desc()).first()
    over, ball_num = 0, 1
    if last_ball:
        over = last_ball.over
        ball_num = last_ball.ball
        if not is_extra:
            ball_num += 1
            if ball_num > 6:
                over += 1
                ball_num = 1

    batsmen = db.query(models.Batsman).filter(models.Batsman.match_id == match_id, models.Batsman.is_out == False).all()
    if len(batsmen) < 2: raise HTTPException(400, "Need 2 batsmen")

    striker = next(b for b in batsmen if b.is_striker)
    non_striker = next(b for b in batsmen if not b.is_striker)

    new_ball = models.Ball(
        match_id=match_id, innings=match.current_innings, over=over, ball=ball_num,
        batsman_id=striker.player_id, non_striker_id=non_striker.player_id,
        runs=runs, extra_type=extra_type, extra_runs=extra_runs,
        is_wicket=wicket, player_out_id=striker.player_id if wicket else None,
        is_legal_ball=not is_extra
    )
    db.add(new_ball)

    if not is_extra: striker.balls += 1
    striker.runs += runs
    if runs == 4:
        striker.fours += 1
    elif runs == 6:
        striker.sixes += 1

    if wicket:
        striker.is_out = True
        striker.is_striker = False
        if not next_batsman_id:
            db.commit()
            return {"need_next_batsman": True}
        player = db.query(models.Player).get(next_batsman_id)
        db.add(models.Batsman(match_id=match_id, player_id=player.id, name=player.name, is_striker=True))
    else:
        if not is_extra and runs % 2 == 1:
            striker.is_striker = False
            non_striker.is_striker = True

    if not is_extra and ball_num == 6:
        striker.is_striker = not striker.is_striker
        non_striker.is_striker = not non_striker.is_striker

    db.commit()
    return {"message": "Ball added", "runs_added": runs + extra_runs, "is_extra": is_extra}


@router.post("/{match_id}/reset")
def reset_match(match_id: str, db: Session = Depends(get_db)):
    db.query(models.Ball).filter(models.Ball.match_id == match_id).delete()
    db.query(models.Batsman).filter(models.Batsman.match_id == match_id).delete()
    db.commit()
    return {"message": "Match reset"}


def update_points(db, tournament_id, team_name, runs_scored, overs_faced, runs_conceded, overs_bowled, is_winner):
    p = db.query(TournamentPoints).filter_by(tournament_id=tournament_id, team_name=team_name).first()
    if not p: return
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
        match_id: str,
        team_a_runs: int, team_a_overs: float,
        team_b_runs: int, team_b_overs: float,
        winner: str,
        db: Session = Depends(get_db)
):
    match = db.query(TournamentMatch).get(match_id)
    if match.winner: return {"message": "Result already submitted"}
    match.winner = winner

    update_points(db, match.tournament_id, match.team_a, team_a_runs, team_a_overs, team_b_runs, team_b_overs,
                  is_winner=(winner == match.team_a))
    update_points(db, match.tournament_id, match.team_b, team_b_runs, team_b_overs, team_a_runs, team_a_overs,
                  is_winner=(winner == match.team_b))

    db.commit()
    return {"message": "Result updated successfully"}


@router.post("/{match_id}/next_batsman")
def select_next_batsman(
        match_id: str, player_id: str,
        db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)
):
    match = db.query(models.Match).get(match_id)
    if match.admin_id != user_id: raise HTTPException(403, "Not allowed")

    batting_team_id = match.team_a_id if match.current_innings == 1 else match.team_b_id
    team_players = db.query(models.TeamPlayer).filter(models.TeamPlayer.team_id == batting_team_id).all()
    if player_id not in [tp.player_id for tp in team_players]: raise HTTPException(400, "Invalid player")

    if db.query(models.Batsman).filter(models.Batsman.match_id == match_id,
                                       models.Batsman.player_id == player_id).first():
        raise HTTPException(400, "Already batted")

    player = db.query(models.Player).get(player_id)
    db.add(models.Batsman(match_id=match_id, player_id=player.id, name=player.name, is_striker=True))
    db.commit()
    return {"message": "New batsman added"}


@router.post("/{match_id}/set_bowler")
def set_bowler(
        match_id: str, player_id: str,
        db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)
):
    match = db.query(models.Match).get(match_id)
    if match.admin_id != user_id: raise HTTPException(403, "Not allowed")

    player = db.query(models.Player).get(player_id)
    if not player: raise HTTPException(404, "Player not found")

    db.add(models.Bowler(match_id=match_id, player_id=player.id, name=player.name, overs="0.0", runs=0, wickets=0,
                         economy=0))
    db.commit()
    return {"message": "Bowler set"}


@router.delete("/{match_id}/undo_ball")
def undo_ball(
        match_id: str,
        db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)
):
    match = db.query(models.Match).get(match_id)
    if match.admin_id != user_id: raise HTTPException(403, "Not allowed")

    last_ball = db.query(models.Ball).filter(models.Ball.match_id == match_id).order_by(models.Ball.id.desc()).first()
    if not last_ball: raise HTTPException(400, "No balls to undo")

    db.delete(last_ball)
    db.commit()
    return {"message": "Last ball removed"}


@router.post("/{match_id}/next_innings")
def next_innings(match_id: str, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    match = db.query(models.Match).get(match_id)
    if match.admin_id != user_id: raise HTTPException(403, "Not allowed")
    if match.current_innings == 2: raise HTTPException(400, "Match already finished")

    match.current_innings = 2
    db.commit()
    return {"message": "Second innings started"}


@router.get("/{match_id}/yet_to_bat")
def get_yet_to_bat(match_id: str, db: Session = Depends(get_db)):
    match = db.query(models.Match).get(match_id)
    if not match: raise HTTPException(404, "Match not found")

    team_players = db.query(models.Player.id, models.Player.name).join(
        models.TeamPlayer, models.TeamPlayer.player_id == models.Player.id
    ).filter(models.TeamPlayer.team_id == match.team_a_id).all()

    batted = db.query(models.Batsman.player_id).filter(models.Batsman.match_id == match_id).all()
    batted_ids = [b[0] for b in batted]

    result = [{"id": p.id, "name": p.name} for p in team_players if p.id not in batted_ids]
    return {"players": result}


@router.post("/{match_id}/finish")
def finish_match(match_id: str, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    match = db.query(models.Match).get(match_id)
    if match.admin_id != user_id: raise HTTPException(403, "Not allowed")

    balls = db.query(models.Ball).filter(models.Ball.match_id == match_id).all()
    total_runs = sum((b.runs or 0) + (b.extra_runs or 0) for b in balls)

    match.status = "completed"
    match.scoreA = str(total_runs)
    db.commit()
    return {"message": "Match completed"}