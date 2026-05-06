from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database.db import get_db

from app.database.models import (
    Team,
    Player,
    TeamPlayer,
    TournamentTeam,
    GroupTeam,
    TeamInvite,
    TournamentMatch, generate_uuid,
)



router = APIRouter(prefix="/teams")


#######################################################################
# CREATE TEAM
#######################################################################

@router.post("/create")
def create_team(
    body: dict,
    db: Session = Depends(get_db)
):

    name = body.get("name")
    captain_id = body.get("captain_id")

    if not name:
        raise HTTPException(
            status_code=400,
            detail="Team name required"
        )

    ###############################################################
    # DUPLICATE CHECK
    ###############################################################

    existing = db.query(Team).filter(
        Team.name.ilike(name)
    ).first()

    if existing:
        return {
            "id": existing.id,
            "name": existing.name,
            "captain_id": existing.captain_id
        }

    ###############################################################
    # CREATE
    ###############################################################

    team = Team(
        id=generate_uuid(),
        name=name,
        captain_id=captain_id
    )

    db.add(team)

    db.commit()

    db.refresh(team)

    return {
        "id": team.id,
        "name": team.name,
        "captain_id": team.captain_id
    }


#######################################################################
# GET TEAM
#######################################################################

@router.get("/{team_id}")
def get_team(
    team_id: str,
    db: Session = Depends(get_db)
):

    team = db.query(Team).filter(
        Team.id == team_id
    ).first()

    if not team:
        raise HTTPException(
            status_code=404,
            detail="Team not found"
        )

    return {
        "id": team.id,
        "name": team.name,
        "captain_id": team.captain_id
    }


#######################################################################
# GET TEAM PLAYERS
#######################################################################

@router.get("/{team_id}/players")
def get_team_players(
    team_id: str,
    db: Session = Depends(get_db)
):

    ###############################################################
    # TEAM EXISTS
    ###############################################################

    team = db.query(Team).filter(
        Team.id == team_id
    ).first()

    if not team:
        raise HTTPException(
            status_code=404,
            detail="Team not found"
        )

    ###############################################################
    # TEAM PLAYERS
    ###############################################################

    team_players = db.query(TeamPlayer).filter(
        TeamPlayer.team_id == team_id
    ).all()

    result = []

    for tp in team_players:

        player = db.query(Player).filter(
            Player.id == tp.player_id
        ).first()

        if not player:
            continue

        result.append({
            "id": player.id,
            "name": player.name,
            "phone": player.phone,
            "email": player.email,
        })

    return result


#######################################################################
# QUICK ADD PLAYER
#######################################################################

@router.post("/players/quick_add")
def quick_add_player(
    body: dict,
    db: Session = Depends(get_db)
):

    ###############################################################
    # DATA
    ###############################################################

    team_id = body.get("team_id")
    name = body.get("name")
    phone = body.get("phone")

    ###############################################################
    # VALIDATE
    ###############################################################

    if not team_id:
        raise HTTPException(
            status_code=400,
            detail="team_id required"
        )

    if not name:
        raise HTTPException(
            status_code=400,
            detail="name required"
        )

    ###############################################################
    # TEAM EXISTS
    ###############################################################

    team = db.query(Team).filter(
        Team.id == team_id
    ).first()

    if not team:
        raise HTTPException(
            status_code=404,
            detail="Team not found"
        )

    ###############################################################
    # EXISTING PLAYER
    ###############################################################

    player = None

    if phone:

        player = db.query(Player).filter(
            Player.phone == phone
        ).first()

    ###############################################################
    # CREATE PLAYER
    ###############################################################

    if not player:

        player = Player(
            id=generate_uuid(),
            name=name,
            phone=phone
        )

        db.add(player)

        db.flush()

    ###############################################################
    # PREVENT DUPLICATE TEAM PLAYER
    ###############################################################

    existing = db.query(TeamPlayer).filter(
        TeamPlayer.team_id == team_id,
        TeamPlayer.player_id == player.id
    ).first()

    if not existing:

        db.add(
            TeamPlayer(
                id=generate_uuid(),
                team_id=team_id,
                player_id=player.id
            )
        )

    db.commit()

    ###############################################################
    # RESPONSE
    ###############################################################

    return {
        "id": player.id,
        "name": player.name,
        "phone": player.phone
    }


#######################################################################
# SEARCH PLAYERS
#######################################################################

@router.get("/players/search")
def search_players(
    q: str,
    team_id: str,
    db: Session = Depends(get_db)
):

    ###############################################################
    # SEARCH
    ###############################################################

    players = db.query(Player).filter(
        or_(
            Player.phone.ilike(f"%{q}%"),
            Player.name.ilike(f"%{q}%")
        )
    ).limit(20).all()

    result = []

    ###############################################################
    # RESPONSE
    ###############################################################

    for p in players:

        already = db.query(TeamPlayer).filter(
            TeamPlayer.team_id == team_id,
            TeamPlayer.player_id == p.id
        ).first()

        result.append({
            "id": p.id,
            "name": p.name,
            "phone": p.phone,
            "already_in_team":
                already is not None
        })

    return result


#######################################################################
# ADD PLAYER TO TEAM
#######################################################################

@router.post("/{team_id}/players/{player_id}")
def add_player_to_team(
    team_id: str,
    player_id: str,
    db: Session = Depends(get_db)
):

    ###############################################################
    # VALIDATE
    ###############################################################

    team = db.query(Team).filter(
        Team.id == team_id
    ).first()

    if not team:
        raise HTTPException(
            status_code=404,
            detail="Team not found"
        )

    player = db.query(Player).filter(
        Player.id == player_id
    ).first()

    if not player:
        raise HTTPException(
            status_code=404,
            detail="Player not found"
        )

    ###############################################################
    # DUPLICATE CHECK
    ###############################################################

    existing = db.query(TeamPlayer).filter(
        TeamPlayer.team_id == team_id,
        TeamPlayer.player_id == player_id
    ).first()

    if existing:
        return {
            "success": True,
            "message": "Already in team"
        }

    ###############################################################
    # ADD
    ###############################################################

    db.add(
        TeamPlayer(
            id=generate_uuid(),
            team_id=team_id,
            player_id=player_id
        )
    )

    db.commit()

    return {
        "success": True
    }


#######################################################################
# REMOVE PLAYER FROM TEAM
#######################################################################

@router.delete("/{team_id}/players/{player_id}")
def remove_player_from_team(
    team_id: str,
    player_id: str,
    db: Session = Depends(get_db)
):

    row = db.query(TeamPlayer).filter(
        TeamPlayer.team_id == team_id,
        TeamPlayer.player_id == player_id
    ).first()

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Player not in team"
        )

    db.delete(row)

    db.commit()

    return {
        "success": True
    }


#######################################################################
# DELETE TEAM
#######################################################################

@router.delete("/{team_id}")
def delete_team(
    team_id: str,
    db: Session = Depends(get_db)
):

    ###############################################################
    # REMOVE TOURNAMENT LINKS
    ###############################################################

    db.query(TournamentTeam).filter(
        TournamentTeam.team_id == team_id
    ).delete(synchronize_session=False)

    ###############################################################
    # REMOVE GROUP LINKS
    ###############################################################

    db.query(GroupTeam).filter(
        GroupTeam.team_id == team_id
    ).delete(synchronize_session=False)

    ###############################################################
    # REMOVE FIXTURES
    ###############################################################

    db.query(TournamentMatch).filter(
        (TournamentMatch.team_a_id == team_id) |
        (TournamentMatch.team_b_id == team_id)
    ).delete(synchronize_session=False)

    ###############################################################
    # REMOVE INVITES
    ###############################################################

    db.query(TeamInvite).filter(
        TeamInvite.team_id == team_id
    ).delete(synchronize_session=False)

    ###############################################################
    # REMOVE TEAM PLAYERS
    ###############################################################

    db.query(TeamPlayer).filter(
        TeamPlayer.team_id == team_id
    ).delete(synchronize_session=False)

    ###############################################################
    # DELETE TEAM
    ###############################################################

    db.query(Team).filter(
        Team.id == team_id
    ).delete(synchronize_session=False)

    db.commit()

    return {
        "success": True,
        "message": "Team deleted"
    }