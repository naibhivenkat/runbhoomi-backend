
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import models
from app.database.db import get_db

router = APIRouter(prefix="/matches")


@router.post("/create_match")
def create_match(
        tournament_id: str,
        team_a_id: str,
        team_b_id: str,
        overs: int = 20,
        db: Session = Depends(get_db)
):
    match = models.Match(
        team_a_id=team_a_id,
        team_b_id=team_b_id,
        total_overs=overs,
        status="scheduled",
        tournament_id=tournament_id
    )

    db.add(match)
    db.commit()
    db.refresh(match)

    return {
        "match_id": match.id
    }


@router.get("/{match_id}")
def get_match(
        match_id: str,
        db: Session = Depends(get_db)
):
    match = db.query(models.Match).filter(
        models.Match.id == match_id
    ).first()

    ########################################################
    # SAFE CHECK
    ########################################################

    if not match:
        raise HTTPException(
            status_code=404,
            detail="Match not found"
        )

    ########################################################
    # INNINGS
    ########################################################

    innings = db.query(models.MatchInnings).filter(
        models.MatchInnings.match_id == match.id
    ).order_by(
        models.MatchInnings.innings_no.asc()
    ).all()

    innings_data = []

    for inn in innings:
        innings_data.append({
            "innings_no": inn.innings_no,
            "batting_team_id": inn.batting_team_id,
            "bowling_team_id": inn.bowling_team_id,
            "runs": inn.runs,
            "wickets": inn.wickets,
            "overs": inn.overs,
            "target": inn.target
        })

    ########################################################
    # RESPONSE
    ########################################################

    return {
        "id": match.id,

        "status": match.status,

        "target": match.target,

        "current_innings":
            match.current_innings,

        "team_a_id":
            match.team_a_id,

        "team_b_id":
            match.team_b_id,

        "team_a_name":
            match.teamA.name
            if match.teamA else None,

        "team_b_name":
            match.teamB.name
            if match.teamB else None,

        "innings": innings_data,

        "created_at":
            match.created_at
    }




@router.get("/user/{email}")
def get_matches_by_user(
        email: str,
        db: Session = Depends(get_db)
):
    ########################################################
    # FIND PLAYER
    ########################################################
    player = db.query(models.Player).filter(
        models.Player.email == email
    ).first()

    if not player:
        return []

    ########################################################
    # LOAD ALL MATCHES (DESCENDING)
    ########################################################
    all_matches = db.query(models.Match).order_by(
        models.Match.created_at.desc()
    ).all()

    ########################################################
    # FILTER RELEVANT MATCHES
    ########################################################
    matches = []

    for match in all_matches:
        include = False

        # -----------------------------------------------
        # 1. USER IS MATCH ADMIN / SCORER
        # -----------------------------------------------
        if match.admin_id == player.id:
            include = True

        # -----------------------------------------------
        # 2. USER CREATED THE TOURNAMENT
        # -----------------------------------------------
        if (
            not include and
            match.tournament_id
        ):
            tournament = db.query(models.Tournament).filter(
                models.Tournament.id == match.tournament_id
            ).first()

            if (
                tournament and
                tournament.created_by == player.id
            ):
                include = True

        # -----------------------------------------------
        # 3. USER IS TOURNAMENT USER
        # -----------------------------------------------
        if (
            not include and
            match.tournament_id
        ):
            tournament_user = db.query(
                models.TournamentUser
            ).filter(
                models.TournamentUser.tournament_id
                == match.tournament_id,
                models.TournamentUser.user_id
                == player.id
            ).first()

            if tournament_user:
                include = True

        # -----------------------------------------------
        # 4. USER IS TOURNAMENT OFFICIAL
        # -----------------------------------------------
        if (
            not include and
            match.tournament_id
        ):
            official = db.query(
                models.TournamentOfficial
            ).filter(
                models.TournamentOfficial.tournament_id
                == match.tournament_id,
                models.TournamentOfficial.user_id
                == player.id
            ).first()

            if official:
                include = True

        if include:
            matches.append(match)

    ########################################################
    # BUILD RESPONSE
    ########################################################
    data = []

    for match in matches:
        innings = db.query(models.MatchInnings).filter(
            models.MatchInnings.match_id == match.id
        ).order_by(
            models.MatchInnings.innings_no.asc()
        ).all()

        innings_data = []

        for inn in innings:
            innings_data.append({
                "innings_no": inn.innings_no,
                "runs": inn.runs,
                "wickets": inn.wickets,
                "overs": inn.overs,
                "target": inn.target,
            })

        # Tournament fixture winner (for completed matches)
        fixture = db.query(models.TournamentMatch).filter(
            models.TournamentMatch.match_id == match.id
        ).first()

        data.append({
            "id": match.id,
            "status": match.status,
            "target": match.target,
            "max_overs": match.total_overs,
            "current_innings": match.current_innings,

            "teamA":
                match.teamA.name
                if match.teamA else "Team A",

            "teamB":
                match.teamB.name
                if match.teamB else "Team B",

            "teamA_id": match.team_a_id,
            "teamB_id": match.team_b_id,

            "innings": innings_data,

            "created_at": match.created_at,

            # 🔥 CRITICAL FIELDS FOR HOME DASHBOARD
            "result": match.result,
            "winner":
                fixture.winner
                if fixture else None,
            "note": match.note,

            # Permissions
            "is_admin": match.admin_id == player.id,
        })

    return data




