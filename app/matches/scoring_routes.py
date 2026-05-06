# from fastapi import APIRouter, Depends, HTTPException
# from sqlalchemy.orm import Session
# from app.auth.deps import get_current_user_id
# from app.database import models
# from app.database.db import get_db
# from app.database.models import TournamentPoints, TournamentMatch
# from app.utls.match_model import BallInput
#
# router = APIRouter(prefix="/scoring")  # Differentiated prefix
#
#
# @router.post("/{match_id}/start_match")
# def start_match(
#         match_id: str,
#         striker_id: str,
#         non_striker_id: str,
#         db: Session = Depends(get_db),
#         user_id: str = Depends(get_current_user_id)
# ):
#     match = db.query(models.Match).get(match_id)
#     if match.admin_id != user_id:
#         raise HTTPException(403, "Not allowed")
#
#     db.query(models.Batsman).filter(models.Batsman.match_id == match_id).delete()
#     db.query(models.Ball).filter(models.Ball.match_id == match_id).delete()
#
#     striker = db.query(models.Player).get(striker_id)
#     non_striker = db.query(models.Player).get(non_striker_id)
#
#     db.add(models.Batsman(match_id=match_id, player_id=striker.id, name=striker.name, is_striker=True))
#     db.add(models.Batsman(match_id=match_id, player_id=non_striker.id, name=non_striker.name, is_striker=False))
#
#     match.status = "live"
#     db.commit()
#     return {"message": "Match started"}
#
#
# @router.get("/{match_id}/live")
# def get_live_score(match_id: str, db: Session = Depends(get_db)):
#     balls = db.query(models.Ball).filter(models.Ball.match_id == match_id).order_by(models.Ball.id.asc()).all()
#
#     total_runs = sum((b.runs or 0) + (b.extra_runs or 0) for b in balls)
#     wickets = sum(1 for b in balls if b.is_wicket)
#     legal_balls = sum(1 for b in balls if b.is_legal_ball)
#
#     overs = f"{legal_balls // 6}.{legal_balls % 6}"
#     score = f"{total_runs}/{wickets}"
#
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
#     batsmen = db.query(models.Batsman).filter(models.Batsman.match_id == match_id, models.Batsman.is_out == False).all()
#     batsmen_data = [{"name": b.name, "runs": b.runs, "balls": b.balls, "is_striker": b.is_striker} for b in batsmen]
#
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
# @router.post("/{match_id}/add_ball")
# def add_ball(
#         match_id: str,
#         payload: BallInput,
#         db: Session = Depends(get_db),
#         user_id: str = Depends(get_current_user_id)
# ):
#     match = db.query(models.Match).get(match_id)
#     if not match: raise HTTPException(404, "Match not found")
#     if match.admin_id != user_id: raise HTTPException(403, "Not allowed")
#
#     runs = payload.runs or 0
#     wicket = payload.wicket
#     extra_type = payload.extra_type
#     next_batsman_id = payload.next_batsman_id  # Make sure this is a str in BallInput schema
#
#     is_extra = extra_type in ["wide", "no_ball"]
#     extra_runs = 1 if is_extra else 0
#
#     last_ball = db.query(models.Ball).filter(models.Ball.match_id == match_id).order_by(models.Ball.id.desc()).first()
#     over, ball_num = 0, 1
#     if last_ball:
#         over = last_ball.over
#         ball_num = last_ball.ball
#         if not is_extra:
#             ball_num += 1
#             if ball_num > 6:
#                 over += 1
#                 ball_num = 1
#
#     batsmen = db.query(models.Batsman).filter(models.Batsman.match_id == match_id, models.Batsman.is_out == False).all()
#     if len(batsmen) < 2: raise HTTPException(400, "Need 2 batsmen")
#
#     striker = next(b for b in batsmen if b.is_striker)
#     non_striker = next(b for b in batsmen if not b.is_striker)
#
#     new_ball = models.Ball(
#         match_id=match_id, innings=match.current_innings, over=over, ball=ball_num,
#         batsman_id=striker.player_id, non_striker_id=non_striker.player_id,
#         runs=runs, extra_type=extra_type, extra_runs=extra_runs,
#         is_wicket=wicket, player_out_id=striker.player_id if wicket else None,
#         is_legal_ball=not is_extra
#     )
#     db.add(new_ball)
#
#     if not is_extra: striker.balls += 1
#     striker.runs += runs
#     if runs == 4:
#         striker.fours += 1
#     elif runs == 6:
#         striker.sixes += 1
#
#     if wicket:
#         striker.is_out = True
#         striker.is_striker = False
#         if not next_batsman_id:
#             db.commit()
#             return {"need_next_batsman": True}
#         player = db.query(models.Player).get(next_batsman_id)
#         db.add(models.Batsman(match_id=match_id, player_id=player.id, name=player.name, is_striker=True))
#     else:
#         if not is_extra and runs % 2 == 1:
#             striker.is_striker = False
#             non_striker.is_striker = True
#
#     if not is_extra and ball_num == 6:
#         striker.is_striker = not striker.is_striker
#         non_striker.is_striker = not non_striker.is_striker
#
#     db.commit()
#     return {"message": "Ball added", "runs_added": runs + extra_runs, "is_extra": is_extra}
#
#
# @router.post("/{match_id}/reset")
# def reset_match(match_id: str, db: Session = Depends(get_db)):
#     db.query(models.Ball).filter(models.Ball.match_id == match_id).delete()
#     db.query(models.Batsman).filter(models.Batsman.match_id == match_id).delete()
#     db.commit()
#     return {"message": "Match reset"}
#
#
# def update_points(db, tournament_id, team_name, runs_scored, overs_faced, runs_conceded, overs_bowled, is_winner):
#     p = db.query(TournamentPoints).filter_by(tournament_id=tournament_id, team_name=team_name).first()
#     if not p: return
#     p.played += 1
#     p.runs_scored += runs_scored
#     p.overs_faced += overs_faced
#     p.runs_conceded += runs_conceded
#     p.overs_bowled += overs_bowled
#     if is_winner:
#         p.wins += 1
#         p.points += 2
#     else:
#         p.losses += 1
#
#
# @router.post("/{match_id}/result")
# def update_result(
#         match_id: str,
#         team_a_runs: int, team_a_overs: float,
#         team_b_runs: int, team_b_overs: float,
#         winner: str,
#         db: Session = Depends(get_db)
# ):
#     match = db.query(TournamentMatch).get(match_id)
#     if match.winner: return {"message": "Result already submitted"}
#     match.winner = winner
#
#     update_points(db, match.tournament_id, match.team_a, team_a_runs, team_a_overs, team_b_runs, team_b_overs,
#                   is_winner=(winner == match.team_a))
#     update_points(db, match.tournament_id, match.team_b, team_b_runs, team_b_overs, team_a_runs, team_a_overs,
#                   is_winner=(winner == match.team_b))
#
#     db.commit()
#     return {"message": "Result updated successfully"}
#
#
# @router.post("/{match_id}/next_batsman")
# def select_next_batsman(
#         match_id: str, player_id: str,
#         db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)
# ):
#     match = db.query(models.Match).get(match_id)
#     if match.admin_id != user_id: raise HTTPException(403, "Not allowed")
#
#     batting_team_id = match.team_a_id if match.current_innings == 1 else match.team_b_id
#     team_players = db.query(models.TeamPlayer).filter(models.TeamPlayer.team_id == batting_team_id).all()
#     if player_id not in [tp.player_id for tp in team_players]: raise HTTPException(400, "Invalid player")
#
#     if db.query(models.Batsman).filter(models.Batsman.match_id == match_id,
#                                        models.Batsman.player_id == player_id).first():
#         raise HTTPException(400, "Already batted")
#
#     player = db.query(models.Player).get(player_id)
#     db.add(models.Batsman(match_id=match_id, player_id=player.id, name=player.name, is_striker=True))
#     db.commit()
#     return {"message": "New batsman added"}
#
#
# @router.post("/{match_id}/set_bowler")
# def set_bowler(
#         match_id: str, player_id: str,
#         db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)
# ):
#     match = db.query(models.Match).get(match_id)
#     if match.admin_id != user_id: raise HTTPException(403, "Not allowed")
#
#     player = db.query(models.Player).get(player_id)
#     if not player: raise HTTPException(404, "Player not found")
#
#     db.add(models.Bowler(match_id=match_id, player_id=player.id, name=player.name, overs="0.0", runs=0, wickets=0,
#                          economy=0))
#     db.commit()
#     return {"message": "Bowler set"}
#
#
# @router.delete("/{match_id}/undo_ball")
# def undo_ball(
#         match_id: str,
#         db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)
# ):
#     match = db.query(models.Match).get(match_id)
#     if match.admin_id != user_id: raise HTTPException(403, "Not allowed")
#
#     last_ball = db.query(models.Ball).filter(models.Ball.match_id == match_id).order_by(models.Ball.id.desc()).first()
#     if not last_ball: raise HTTPException(400, "No balls to undo")
#
#     db.delete(last_ball)
#     db.commit()
#     return {"message": "Last ball removed"}
#
#
# @router.post("/{match_id}/next_innings")
# def next_innings(match_id: str, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
#     match = db.query(models.Match).get(match_id)
#     if match.admin_id != user_id: raise HTTPException(403, "Not allowed")
#     if match.current_innings == 2: raise HTTPException(400, "Match already finished")
#
#     match.current_innings = 2
#     db.commit()
#     return {"message": "Second innings started"}
#
#
# @router.get("/{match_id}/yet_to_bat")
# def get_yet_to_bat(match_id: str, db: Session = Depends(get_db)):
#     match = db.query(models.Match).get(match_id)
#     if not match: raise HTTPException(404, "Match not found")
#
#     team_players = db.query(models.Player.id, models.Player.name).join(
#         models.TeamPlayer, models.TeamPlayer.player_id == models.Player.id
#     ).filter(models.TeamPlayer.team_id == match.team_a_id).all()
#
#     batted = db.query(models.Batsman.player_id).filter(models.Batsman.match_id == match_id).all()
#     batted_ids = [b[0] for b in batted]
#
#     result = [{"id": p.id, "name": p.name} for p in team_players if p.id not in batted_ids]
#     return {"players": result}
#
#
# @router.post("/{match_id}/finish")
# def finish_match(match_id: str, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
#     match = db.query(models.Match).get(match_id)
#     if match.admin_id != user_id: raise HTTPException(403, "Not allowed")
#
#     balls = db.query(models.Ball).filter(models.Ball.match_id == match_id).all()
#     total_runs = sum((b.runs or 0) + (b.extra_runs or 0) for b in balls)
#
#     match.status = "completed"
#     match.scoreA = str(total_runs)
#     db.commit()
#     return {"message": "Match completed"}


from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import models
from app.database.db import get_db
from app.database.models import generate_uuid
from app.matches.innings_service import get_current_innings, complete_innings, create_second_innings, \
    calculate_innings_score
from app.matches.match_service import resolve_match

router = APIRouter(prefix="/scoring")


@router.post("/{match_id}/start")
def start_match(
        match_id: str,
        striker_id: str,
        non_striker_id: str,
        bowler_id: str,
        db: Session = Depends(get_db)
):
    match = resolve_match(db, match_id)

    existing = db.query(models.MatchInnings).filter(
        models.MatchInnings.match_id == match.id
    ).first()

    if existing:
        return {
            "message": "Already started"
        }

    innings = models.MatchInnings(
        id=generate_uuid(),
        match_id=match.id,
        innings_no=1,
        batting_team_id=match.team_a_id,
        bowling_team_id=match.team_b_id,
        status="live"
    )

    db.add(innings)

    striker = db.query(models.Player).get(striker_id)
    non_striker = db.query(models.Player).get(non_striker_id)
    bowler = db.query(models.Player).get(bowler_id)

    db.add(models.Batsman(
        id=generate_uuid(),
        match_id=match.id,
        innings_id=innings.id,
        player_id=striker.id,
        team_id=innings.batting_team_id,
        name=striker.name,
        is_striker=True
    ))

    db.add(models.Batsman(
        id=generate_uuid(),
        match_id=match.id,
        innings_id=innings.id,
        player_id=non_striker.id,
        team_id=innings.batting_team_id,
        name=non_striker.name,
        is_striker=False
    ))

    db.add(models.Bowler(
        id=generate_uuid(),
        match_id=match.id,
        innings_id=innings.id,
        player_id=bowler.id,
        team_id=innings.bowling_team_id,
        name=bowler.name
    ))

    match.status = "live"

    db.commit()

    return {
        "message": "Match started"
    }


@router.post("/{match_id}/ball")
def add_ball(
        match_id: str,
        runs: int = 0,
        extra_type: str = None,
        wicket: bool = False,
        next_batsman_id: str = None,
        bowler_id: str = None,
        wicket_type: str = None,
        db: Session = Depends(get_db)
):
    # =====================================================
    # MATCH
    # =====================================================

    match = resolve_match(db, match_id)

    innings = get_current_innings(db, match.id)

    # =====================================================
    # CURRENT BALL STATE
    # =====================================================

    balls = db.query(models.Ball).filter(
        models.Ball.innings_id == innings.id
    ).all()

    legal_balls = sum(
        1 for b in balls if b.is_legal_ball
    )

    over = legal_balls // 6

    ball = (legal_balls % 6) + 1

    # =====================================================
    # ACTIVE BATSMEN
    # =====================================================

    batsmen = db.query(models.Batsman).filter(
        models.Batsman.innings_id == innings.id,
        models.Batsman.is_out == False
    ).all()

    striker = next(
        (b for b in batsmen if b.is_striker),
        None
    )

    non_striker = next(
        (b for b in batsmen if not b.is_striker),
        None
    )

    if not striker or not non_striker:
        raise HTTPException(
            400,
            "Both striker and non-striker required"
        )

    # =====================================================
    # BOWLER VALIDATION
    # =====================================================

    if not bowler_id:
        raise HTTPException(
            400,
            "Bowler required"
        )

    current_bowler = db.query(models.Bowler).filter(
        models.Bowler.innings_id == innings.id,
        models.Bowler.player_id == bowler_id
    ).first()

    if not current_bowler:
        player = db.query(models.Player).get(bowler_id)

        current_bowler = models.Bowler(
            id=generate_uuid(),
            match_id=match.id,
            innings_id=innings.id,
            player_id=player.id,
            team_id=innings.bowling_team_id,
            name=player.name
        )

        db.add(current_bowler)

    # =====================================================
    # EXTRA TYPES
    # =====================================================

    is_wide = extra_type == "wide"

    is_no_ball = extra_type == "no_ball"

    is_bye = extra_type == "bye"

    is_legbye = extra_type == "legbye"

    is_extra = extra_type in [
        "wide",
        "no_ball",
        "bye",
        "legbye"
    ]

    is_legal_ball = not (
        is_wide or is_no_ball
    )

    # =====================================================
    # TOTAL BALL RUNS
    # =====================================================

    extra_runs = 0

    if is_wide or is_no_ball:
        extra_runs = 1

    total_runs = runs + extra_runs

    # =====================================================
    # SAVE BALL
    # =====================================================

    new_ball = models.Ball(
        id=generate_uuid(),

        match_id=match.id,

        innings_id=innings.id,

        over=over,

        ball=ball,

        batsman_id=striker.player_id,

        non_striker_id=non_striker.player_id,

        bowler_id=bowler_id,

        runs=runs,

        extra_type=extra_type,

        extra_runs=extra_runs,

        is_wicket=wicket,

        wicket_type=wicket_type,

        player_out_id=(
            striker.player_id
            if wicket else None
        ),

        is_legal_ball=is_legal_ball
    )

    db.add(new_ball)

    # =====================================================
    # BATSMAN STATS
    # =====================================================

    if not is_wide and not is_bye and not is_legbye:
        striker.runs += runs

    if is_legal_ball:
        striker.balls += 1

    if runs == 4:
        striker.fours += 1

    if runs == 6:
        striker.sixes += 1

    # =====================================================
    # WICKET HANDLING
    # =====================================================

    if wicket:

        striker.is_out = True

        striker.is_striker = False

        # =============================================
        # NEXT BATSMAN
        # =============================================

        if next_batsman_id:

            existing_batsman = db.query(
                models.Batsman
            ).filter(
                models.Batsman.innings_id == innings.id,
                models.Batsman.player_id == next_batsman_id
            ).first()

            if existing_batsman:
                raise HTTPException(
                    400,
                    "Batsman already used"
                )

            p = db.query(models.Player).get(
                next_batsman_id
            )

            if not p:
                raise HTTPException(
                    404,
                    "Next batsman not found"
                )

            new_batter = models.Batsman(
                id=generate_uuid(),

                match_id=match.id,

                innings_id=innings.id,

                player_id=p.id,

                team_id=innings.batting_team_id,

                name=p.name,

                is_striker=True
            )

            db.add(new_batter)

    # =====================================================
    # STRIKE ROTATION
    # =====================================================

    else:

        if runs % 2 == 1:

            striker.is_striker = False

            non_striker.is_striker = True

    # =====================================================
    # OVER END STRIKE CHANGE
    # =====================================================

    next_legal_balls = legal_balls + (
        1 if is_legal_ball else 0
    )

    if next_legal_balls % 6 == 0:

        striker.is_striker = not striker.is_striker

        non_striker.is_striker = (
            not non_striker.is_striker
        )

    # =====================================================
    # RECALCULATE SCORE
    # =====================================================

    score = calculate_innings_score(
        db,
        innings.id
    )

    innings.runs = score["runs"]

    innings.wickets = score["wickets"]

    innings.overs = score["overs"]

    # =====================================================
    # AUTO MATCH COMPLETE
    # =====================================================

    if innings.innings_no == 2:

        target = innings.target or 0

        if innings.runs >= target:

            from app.matches.result_service import (
                complete_match
            )

            complete_match(
                match,
                innings
            )

            db.commit()

            return {
                "message": "Match completed",
                "result": match.result,
                "winner_team_id":
                    match.winner_team_id
            }

    # =====================================================
    # ALL OUT
    # =====================================================

    if innings.wickets >= 10:

        if innings.innings_no == 1:

            innings.status = "completed"

        else:

            from app.matches import (
                complete_match
            )

            complete_match(
                match,
                innings
            )

            db.commit()

            return {
                "message": "Match completed",
                "result": match.result
            }

    # =====================================================
    # OVERS COMPLETE
    # =====================================================

    overs_split = innings.overs.split(".")

    completed_overs = int(
        overs_split[0]
    )

    if completed_overs >= match.total_overs:

        if innings.innings_no == 1:

            innings.status = "completed"

        else:

            from app.matches.result_service import (
                complete_match
            )

            complete_match(
                match,
                innings
            )

            db.commit()

            return {
                "message": "Match completed",
                "result": match.result
            }

    # =====================================================
    # SAVE
    # =====================================================

    db.commit()

    # =====================================================
    # RESPONSE
    # =====================================================

    return {

        "score":
            f"{innings.runs}/{innings.wickets}",

        "overs":
            innings.overs,

        "innings":
            innings.innings_no,

        "target":
            innings.target,

        "striker": {
            "id": striker.player_id,
            "name": striker.name,
            "runs": striker.runs,
            "balls": striker.balls
        },

        "non_striker": {
            "id": non_striker.player_id,
            "name": non_striker.name,
            "runs": non_striker.runs,
            "balls": non_striker.balls
        },

        "last_ball": {
            "runs": runs,
            "extra_type": extra_type,
            "wicket": wicket
        }
    }

@router.post("/{match_id}/end_innings")
def end_innings(
        match_id: str,
        db: Session = Depends(get_db)
):
    match = resolve_match(db, match_id)

    innings = get_current_innings(db, match.id)

    complete_innings(db, innings)

    if innings.innings_no == 1:
        innings2 = create_second_innings(
            db,
            match,
            innings
        )

        db.commit()

        return {
            "target": innings2.target
        }

    match.status = "completed"

    db.commit()

    return {
        "message": "Match completed"
    }