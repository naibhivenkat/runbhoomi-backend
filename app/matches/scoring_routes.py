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
        body: dict,
        db: Session = Depends(get_db)
):
    ########################################################
    # MATCH
    ########################################################

    match = resolve_match(db, match_id)

    ########################################################
    # BODY
    ########################################################

    striker_id = body.get("striker_id")

    non_striker_id = body.get(
        "non_striker_id"
    )

    bowler_id = body.get(
        "bowler_id"
    )

    ########################################################
    # VALIDATE
    ########################################################

    if not striker_id:
        raise HTTPException(
            400,
            "striker_id required"
        )

    if not non_striker_id:
        raise HTTPException(
            400,
            "non_striker_id required"
        )

    if not bowler_id:
        raise HTTPException(
            400,
            "bowler_id required"
        )

    ########################################################
    # ALREADY STARTED
    ########################################################

    existing = db.query(
        models.MatchInnings
    ).filter(
        models.MatchInnings.match_id
        == match.id
    ).first()

    if existing:
        return {
            "message":
                "Already started"
        }

    ########################################################
    # CREATE INNINGS
    ########################################################

    innings = models.MatchInnings(
        id=generate_uuid(),

        match_id=match.id,

        innings_no=1,

        batting_team_id=match.team_a_id,

        bowling_team_id=match.team_b_id,

        status="live"
    )

    db.add(innings)

    ########################################################
    # PLAYERS
    ########################################################

    striker = db.query(
        models.Player
    ).get(striker_id)

    non_striker = db.query(
        models.Player
    ).get(non_striker_id)

    bowler = db.query(
        models.Player
    ).get(bowler_id)

    if not striker:
        raise HTTPException(
            404,
            "Striker not found"
        )

    if not non_striker:
        raise HTTPException(
            404,
            "Non striker not found"
        )

    if not bowler:
        raise HTTPException(
            404,
            "Bowler not found"
        )

    ########################################################
    # BATSMEN
    ########################################################

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

    ########################################################
    # BOWLER
    ########################################################

    db.add(models.Bowler(
        id=generate_uuid(),

        match_id=match.id,

        innings_id=innings.id,

        player_id=bowler.id,

        team_id=innings.bowling_team_id,

        name=bowler.name
    ))

    ########################################################
    # MATCH STATUS
    ########################################################

    match.status = "live"

    db.commit()

    return {
        "success": True,
        "innings_id": innings.id
    }


@router.post("/{match_id}/ball")
def add_ball(
        match_id: str,
        body: dict,
        db: Session = Depends(get_db)
):
    # =====================================================
    # BODY
    # =====================================================

    runs = int(body.get("runs", 0))

    extra_type = body.get("extra_type")

    wicket = bool(body.get("wicket", False))

    next_batsman_id = body.get(
        "next_batsman_id"
    )

    bowler_id = body.get("bowler_id")

    wicket_type = body.get(
        "wicket_type"
    )

    # =====================================================
    # MATCH
    # =====================================================

    match = resolve_match(db, match_id)

    innings = get_current_innings(
        db,
        match.id
    )

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

    current_bowler = db.query(
        models.Bowler
    ).filter(
        models.Bowler.innings_id == innings.id,
        models.Bowler.player_id == bowler_id
    ).first()

    if not current_bowler:

        player = db.query(
            models.Player
        ).get(bowler_id)

        if not player:
            raise HTTPException(
                404,
                "Bowler not found"
            )

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

    is_legal_ball = not (
            is_wide or is_no_ball
    )

    # =====================================================
    # RUNS
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
    # BOWLER STATS
    # =====================================================

    current_bowler.runs = (
                                  current_bowler.runs or 0
                          ) + total_runs

    if wicket:
        current_bowler.wickets = (
                                         current_bowler.wickets or 0
                                 ) + 1

    if is_legal_ball:
        current_bowler.balls = (
                                       current_bowler.balls or 0
                               ) + 1

        overs = (
                current_bowler.balls // 6
        )

        balls_rem = (
                current_bowler.balls % 6
        )

        current_bowler.overs = (
            f"{overs}.{balls_rem}"
        )

    # =====================================================
    # WICKET
    # =====================================================

    if wicket:

        striker.is_out = True

        striker.is_striker = False

        if next_batsman_id:

            existing_batsman = db.query(
                models.Batsman
            ).filter(
                models.Batsman.innings_id
                == innings.id,

                models.Batsman.player_id
                == next_batsman_id
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

            db.add(models.Batsman(
                id=generate_uuid(),

                match_id=match.id,

                innings_id=innings.id,

                player_id=p.id,

                team_id=innings.batting_team_id,

                name=p.name,

                is_striker=True
            ))

    else:

        # =================================================
        # STRIKE CHANGE
        # =================================================

        if runs % 2 == 1:
            striker.is_striker = False

            non_striker.is_striker = True

    # =====================================================
    # OVER COMPLETE STRIKE CHANGE
    # =====================================================

    next_legal_balls = legal_balls + (
        1 if is_legal_ball else 0
    )

    if next_legal_balls % 6 == 0:
        striker.is_striker = (
            not striker.is_striker
        )

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


@router.post("/{match_id}/end_match")
def end_match(match_id: str, db: Session = Depends(get_db)):
    # ---------------------------------------------------
    # RESOLVE MATCH OR TOURNAMENT FIXTURE ID
    # ---------------------------------------------------
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
        raise HTTPException(
            status_code=404,
            detail="Match not found"
        )

    # ---------------------------------------------------
    # CALCULATE FINAL SCORE FROM ALL BALLS
    # ---------------------------------------------------
    balls = db.query(models.Ball).filter(
        models.Ball.match_id == match.id
    ).all()

    total_runs = sum(
        (b.runs or 0) + (b.extra_runs or 0)
        for b in balls
    )

    wickets = sum(
        1 for b in balls if b.is_wicket
    )

    # ---------------------------------------------------
    # DEFAULT RESULT
    # ---------------------------------------------------
    result = "Match tied"
    winner_name = None
    winner_team_id = None

    # ---------------------------------------------------
    # LOAD INNINGS
    # ---------------------------------------------------
    innings_list = db.query(
        models.MatchInnings
    ).filter(
        models.MatchInnings.match_id == match.id
    ).order_by(
        models.MatchInnings.innings_no
    ).all()

    # ---------------------------------------------------
    # TEAM NAMES
    # ---------------------------------------------------
    team_a_name = (
        match.teamA.name
        if getattr(match, "teamA", None)
        else "Team A"
    )

    team_b_name = (
        match.teamB.name
        if getattr(match, "teamB", None)
        else "Team B"
    )

    # ---------------------------------------------------
    # RESULT LOGIC (2 INNINGS MATCH)
    # ---------------------------------------------------
    if len(innings_list) >= 2:
        first_innings = innings_list[0]
        second_innings = innings_list[1]

        first_runs = first_innings.runs or 0
        second_runs = second_innings.runs or 0
        second_wickets = second_innings.wickets or 0

        # Chasing team = batting team in innings 2
        if second_innings.batting_team_id == match.team_a_id:
            chasing_team_name = team_a_name
            chasing_team_id = match.team_a_id
        else:
            chasing_team_name = team_b_name
            chasing_team_id = match.team_b_id

        # Defending team = batting team in innings 1
        if first_innings.batting_team_id == match.team_a_id:
            defending_team_name = team_a_name
            defending_team_id = match.team_a_id
        else:
            defending_team_name = team_b_name
            defending_team_id = match.team_b_id

        # -------------------------------
        # CHASING TEAM WINS
        # Example: RCB won by 7 wickets
        # -------------------------------
        if second_runs > first_runs:
            wickets_remaining = max(1, 10 - second_wickets)

            # Optional premium enhancement:
            # balls_remaining = ...
            # result = f"{chasing_team_name} won by {wickets_remaining} wickets with {balls_remaining} balls remaining"

            result = (
                f"{chasing_team_name} won by "
                f"{wickets_remaining} wicket"
                f"{'' if wickets_remaining == 1 else 's'}"
            )

            winner_name = chasing_team_name
            winner_team_id = chasing_team_id

        # -------------------------------
        # DEFENDING TEAM WINS
        # Example: SRH won by 12 runs
        # -------------------------------
        elif second_runs < first_runs:
            runs_margin = first_runs - second_runs

            result = (
                f"{defending_team_name} won by "
                f"{runs_margin} run"
                f"{'' if runs_margin == 1 else 's'}"
            )

            winner_name = defending_team_name
            winner_team_id = defending_team_id

        # -------------------------------
        # MATCH TIED
        # -------------------------------
        else:
            result = "Match tied"

    # ---------------------------------------------------
    # FALLBACK FOR SINGLE-INNINGS OR ABANDONED MATCHES
    # ---------------------------------------------------
    elif len(innings_list) == 1:
        result = "Match completed"

    # ---------------------------------------------------
    # UPDATE MATCH TABLE
    # ---------------------------------------------------
    match.status = "completed"
    match.current_innings = len(innings_list)
    match.result = result
    match.note = result

    # Final score from the last innings (more meaningful)
    if innings_list:
        last_innings = innings_list[-1]
        match.final_score = (
            f"{last_innings.runs or 0}/"
            f"{last_innings.wickets or 0}"
        )
    else:
        match.final_score = f"{total_runs}/{wickets}"

    # Save winner references
    match.winner_team_id = winner_team_id

    # ---------------------------------------------------
    # UPDATE TOURNAMENT FIXTURE
    # ---------------------------------------------------
    fixture = db.query(models.TournamentMatch).filter(
        models.TournamentMatch.match_id == match.id
    ).first()

    if fixture:
        fixture.winner = winner_name

    # ---------------------------------------------------
    # SAVE
    # ---------------------------------------------------
    db.commit()
    db.refresh(match)

    # ---------------------------------------------------
    # RESPONSE
    # ---------------------------------------------------
    return {
        "message": "Match completed",
        "match_id": match.id,
        "status": match.status,
        "winner": winner_name,
        "winner_team_id": winner_team_id,
        "result": result,
        "final_score": match.final_score,
        "target": match.target,
    }



@router.post("/{match_id}/start_second_innings")
def start_second_innings(
        match_id: str,
        body: dict,
        db: Session = Depends(get_db)
):
    """
    Initialize striker, non-striker and bowler for innings 2.

    This endpoint must be called immediately after the user selects
    the two opening batters and the opening bowler for the chase.
    """

    ########################################################
    # MATCH
    ########################################################

    match = resolve_match(db, match_id)

    ########################################################
    # CURRENT INNINGS (should be innings 2 and live)
    ########################################################

    innings = get_current_innings(db, match.id)

    if innings.innings_no != 2:
        raise HTTPException(
            400,
            "Second innings not available"
        )

    ########################################################
    # BODY
    ########################################################

    striker_id = body.get("striker_id")
    non_striker_id = body.get("non_striker_id")
    bowler_id = body.get("bowler_id")

    ########################################################
    # VALIDATION
    ########################################################

    if not striker_id:
        raise HTTPException(400, "striker_id required")

    if not non_striker_id:
        raise HTTPException(400, "non_striker_id required")

    if not bowler_id:
        raise HTTPException(400, "bowler_id required")

    if striker_id == non_striker_id:
        raise HTTPException(
            400,
            "Striker and non-striker must be different"
        )

    ########################################################
    # ALREADY INITIALIZED?
    ########################################################

    existing_batsmen = db.query(models.Batsman).filter(
        models.Batsman.innings_id == innings.id
    ).count()

    if existing_batsmen >= 2:
        return {
            "success": True,
            "message": "Second innings already initialized",
            "innings_id": innings.id
        }

    ########################################################
    # PLAYERS
    ########################################################

    striker = db.query(models.Player).get(striker_id)
    non_striker = db.query(models.Player).get(non_striker_id)
    bowler = db.query(models.Player).get(bowler_id)

    if not striker:
        raise HTTPException(404, "Striker not found")

    if not non_striker:
        raise HTTPException(404, "Non-striker not found")

    if not bowler:
        raise HTTPException(404, "Bowler not found")

    ########################################################
    # CREATE OPENING BATSMEN
    ########################################################

    db.add(models.Batsman(
        id=generate_uuid(),
        match_id=match.id,
        innings_id=innings.id,
        player_id=striker.id,
        team_id=innings.batting_team_id,
        name=striker.name,
        is_striker=True,
        is_out=False,
        runs=0,
        balls=0,
        fours=0,
        sixes=0
    ))

    db.add(models.Batsman(
        id=generate_uuid(),
        match_id=match.id,
        innings_id=innings.id,
        player_id=non_striker.id,
        team_id=innings.batting_team_id,
        name=non_striker.name,
        is_striker=False,
        is_out=False,
        runs=0,
        balls=0,
        fours=0,
        sixes=0
    ))

    ########################################################
    # CREATE OPENING BOWLER
    ########################################################

    existing_bowler = db.query(models.Bowler).filter(
        models.Bowler.innings_id == innings.id,
        models.Bowler.player_id == bowler.id
    ).first()

    if not existing_bowler:
        db.add(models.Bowler(
            id=generate_uuid(),
            match_id=match.id,
            innings_id=innings.id,
            player_id=bowler.id,
            team_id=innings.bowling_team_id,
            name=bowler.name,
            overs="0.0",
            balls=0,
            runs=0,
            wickets=0
        ))

    ########################################################
    # SAVE
    ########################################################

    db.commit()

    ########################################################
    # RESPONSE
    ########################################################

    return {
        "success": True,
        "message": "Second innings initialized successfully",
        "innings_id": innings.id,
        "target": innings.target
    }

