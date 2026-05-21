import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi import Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user_id
from app.database import models
from app.database.db import get_db
from app.database.models import TournamentTeam, TournamentPoints, TournamentMatch, Team, GroupTeam, TeamInvite, \
    TeamPlayer, TournamentGroup, TournamentUser, TournamentOfficial, Player, generate_uuid
from app.tournaments.group_service import create_groups, generate_knockout, paired_rounds, \
    get_match_duration
from app.utls.permissions import require_admin

router = APIRouter(prefix="/tournaments", tags=["Tournaments"])


class AdminAssignmentPayload(BaseModel):
    player_id: str


class JoinRequestPayload(BaseModel):
    tournament_id: str
    team_name: str
    contact: str
    status: str = "PENDING"


class RenameTournamentPayload(BaseModel):
    new_name: str


class RenameTeamPayload(BaseModel):
    new_name: str


class TournamentCreate(BaseModel):
    id: Optional[str] = None
    name: str
    city: str
    ground: str
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Make these optional so the API doesn't crash if they are missing
    organizer_name: Optional[str] = None
    organizer_phone: Optional[str] = None
    organizer_email: Optional[str] = None

    start_date: str
    end_date: str

    category: str
    ball_type: str
    pitch_type: str
    match_type: str

    total_teams: int
    format: str = "league"
    overs: int = 20

    logo_url: str | None = None
    banner_url: str | None = None


class OfficialAssignRequest(BaseModel):
    id: str
    name: str
    role: str


class UserSearchResponse(BaseModel):
    id: str
    name: str
    phone: str


class OfficialResponse(BaseModel):
    id: str
    name: str
    phone: Optional[str] = None
    role: str


class GroupUpdateRequest(BaseModel):
    group_name: str


class RoleUpdate(BaseModel):
    role: str





@router.post("/create")
def create_tournament(
        payload: TournamentCreate,
        db: Session = Depends(get_db),
        user_id: str = Depends(get_current_user_id)
):
    try:
        new_tournament = models.Tournament(
            name=payload.name,
            city=payload.city,
            ground=payload.ground,
            address=payload.address,
            latitude=payload.latitude,
            longitude=payload.longitude,
            organizer_name=payload.organizer_name,
            organizer_phone=payload.organizer_phone,
            organizer_email=payload.organizer_email,
            start_date=payload.start_date,
            end_date=payload.end_date,
            category=payload.category,
            ball_type=payload.ball_type,
            pitch_type=payload.pitch_type,
            match_type=payload.match_type,
            total_teams=payload.total_teams,
            format=payload.format,
            overs=payload.overs,
            created_by=user_id  # Binds creator as the permanent default Super Admin
        )

        # Preserve the offline-generated UUID from Flutter to avoid synchronization drift
        if payload.id:
            new_tournament.id = payload.id

        db.add(new_tournament)
        db.commit()
        db.refresh(new_tournament)
        return new_tournament
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{tournament_id}/admins/add")
def add_tournament_co_admin(
        tournament_id: str,
        payload: AdminAssignmentPayload,
        db: Session = Depends(get_db),
        current_user_id: str = Depends(get_current_user_id)
):
    """Allows the main tournament creator to add Co-Admins to delegate setup tasks."""
    tournament = db.query(models.Tournament).filter(models.Tournament.id == tournament_id).first()
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament container not found")

    # Security rule: Only the original Super Admin owner can manage access allocations
    if tournament.created_by != current_user_id:
        raise HTTPException(status_code=403, detail="Only the primary creator can add co-admins")

    # Confirm player exists in database registry entries
    player = db.query(models.Player).filter(models.Player.id == payload.player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Target player profile not found")

    # Prevent duplicate entry generation arrays
    already_admin = db.query(models.TournamentAdmin).filter(
        models.TournamentAdmin.tournament_id == tournament_id,
        models.TournamentAdmin.player_id == payload.player_id
    ).first()

    if already_admin or tournament.created_by == payload.player_id:
        return {"message": "User already holds administrative privileges"}

    new_admin = models.TournamentAdmin(
        tournament_id=tournament_id,
        player_id=payload.player_id
    )
    db.add(new_admin)
    db.commit()
    return {"message": f"Successfully registered {player.name} as tournament Co-Admin"}


@router.delete("/{tournament_id}/admins/{player_id}")
def remove_tournament_co_admin(
        tournament_id: str,
        player_id: str,
        db: Session = Depends(get_db),
        current_user_id: str = Depends(get_current_user_id)
):
    """Allows the creator to revoke administrative permissions from a Co-Admin."""
    tournament = db.query(models.Tournament).filter(models.Tournament.id == tournament_id).first()
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament container not found")

    if tournament.created_by != current_user_id:
        raise HTTPException(status_code=403, detail="Only the primary creator can revoke administrative rights")

    admin_link = db.query(models.TournamentAdmin).filter(
        models.TournamentAdmin.tournament_id == tournament_id,
        models.TournamentAdmin.player_id == player_id
    ).first()

    if not admin_link:
        raise HTTPException(status_code=404, detail="Co-admin target linkage not found")

    db.delete(admin_link)
    db.commit()
    return {"message": "Administrative access revoked successfully"}


@router.put("/{tournament_id}/rename")
def rename_tournament(
        tournament_id: str,
        payload: RenameTournamentPayload,
        db: Session = Depends(get_db),
        current_user_id: str = Depends(get_current_user_id)
):
    # 🔒 SECURE: Enforce co-admin verification check instantly
    check_tournament_admin_privileges(tournament_id, current_user_id, db)

    tournament = db.query(models.Tournament).filter(models.Tournament.id == tournament_id).first()
    tournament.name = payload.new_name
    db.commit()
    db.refresh(tournament)
    return tournament


# ==========================================
# 3. DELETE TOURNAMENT ENDPOINT (DELETE)
# ==========================================

@router.delete("/{tournament_id}")
def delete_tournament(
        tournament_id: str,
        db: Session = Depends(get_db),
        current_user_id: str = Depends(get_current_user_id)
):
    tournament = db.query(models.Tournament).filter(models.Tournament.id == tournament_id).first()
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament container not found")

    # 🔒 Owner check remains strict here: co-admins can't delete the entire tournament container!
    if tournament.created_by != current_user_id:
        raise HTTPException(status_code=403,
                            detail="Destructive Error: Only the primary creator can delete this tournament.")

    db.delete(tournament)
    db.commit()
    return {"message": "Tournament context permanently removed from registry"}


@router.post("/matches/{tm_id}/init")
def init_match_from_fixture(tm_id: str, db: Session = Depends(get_db)):
    tm = db.query(models.TournamentMatch).get(tm_id)

    if not tm:
        raise HTTPException(404, "Fixture not found")

    # already created
    if tm.match_id:
        return {"match_id": tm.match_id}

    # ✅ FIX: USE REAL TEAM IDs
    match = models.Match(
        team_a_id=tm.team_a_id,
        team_b_id=tm.team_b_id,
        tournament_id=tm.tournament_id,
        status="created"
    )

    db.add(match)
    db.commit()
    db.refresh(match)

    tm.match_id = match.id
    db.commit()

    return {"match_id": match.id}


@router.post("/{tournament_id}/add_team")
def add_team(tournament_id: str, team_name: str, db: Session = Depends(get_db)):
    tournament = db.query(models.Tournament).filter_by(id=tournament_id).first()

    if not tournament:
        raise HTTPException(404, "Tournament not found")

    # create or get team
    team = db.query(Team).filter_by(name=team_name).first()

    if not team:
        team = Team(name=team_name)
        db.add(team)
        db.commit()
        db.refresh(team)

    # check duplicate
    existing = db.query(TournamentTeam).filter_by(
        tournament_id=tournament_id,
        team_id=team.id
    ).first()

    if existing:
        raise HTTPException(400, "Team already exists")

    # max teams check
    count = db.query(TournamentTeam).filter_by(
        tournament_id=tournament_id
    ).count()

    if count >= tournament.total_teams:
        raise HTTPException(400, "Max teams reached")

    entry = TournamentTeam(
        tournament_id=tournament_id,
        team_id=team.id,
        status="approved"  # ✅ FIX
    )

    db.add(entry)

    db.add(TournamentPoints(
        tournament_id=tournament_id,
        team_id=team.id
    ))

    db.commit()

    return {"message": "Team added"}


@router.put("/teams/{team_id}/rename")
def rename_team(
        team_id: str,
        payload: RenameTeamPayload,
        db: Session = Depends(get_db),
        user_id: str = Depends(get_current_user_id)  # Optional: if you want to verify they are logged in
):
    # Find the team in the database
    team = db.query(Team).filter(Team.id == team_id).first()

    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # Update the name and save
    team.name = payload.new_name
    db.commit()

    return {"status": "success", "message": f"Team renamed to {team.name}"}


@router.get("")
@router.get("/")
def get_tournaments(db: Session = Depends(get_db)):
    tournaments = db.query(models.Tournament).all()

    # return [
    #     {
    #         "id": t.id,
    #         "name": t.name,
    #         "city": t.city,
    #         "ground": t.ground,
    #         "match_type": t.match_type,
    #         "total_teams": t.total_teams,
    #         "start_date": t.start_date,
    #         "end_date": t.end_date,
    #         "banner_url": getattr(t, "banner_url", None),
    #         "logo_url": getattr(t, "logo_url", None),
    #         "created_by": t.created_by
    #     }
    #     for t in tournaments
    # ]
    return [
        {
            "id": t.id,
            "name": t.name,
            "city": t.city,
            "ground": t.ground,
            "address": t.address,
            "latitude": t.latitude,
            "longitude": t.longitude,

            "match_type": t.match_type,

            "total_teams": t.total_teams,

            "format": t.format,
            "overs": t.overs,

            "start_date": t.start_date,
            "end_date": t.end_date,

            "banner_url": getattr(t, "banner_url", None),
            "logo_url": getattr(t, "logo_url", None),

            "created_by": t.created_by
        }
        for t in tournaments
    ]


@router.post("/{tournament_id}/generate_fixtures")
def generate_fixtures(
        tournament_id: str,
        group_count: int = Query(1),
        start_time: str = Query("08:00"),
        gap: int = Query(10),
        is_double_round: bool = Query(False),  # 🔥 ADD THIS PARAMETER
        db: Session = Depends(get_db),
        user_id: str = Depends(get_current_user_id)
):
    require_admin(db, user_id, tournament_id)
    tournament = db.query(models.Tournament).get(tournament_id)
    if not tournament:
        raise HTTPException(404, "Tournament not found")

    teams = db.query(TournamentTeam).filter_by(
        tournament_id=tournament_id, status="approved"
    ).all()

    if len(teams) < 2:
        raise HTTPException(400, "Not enough approved teams")

    # 1. CLEANUP (Matches, Groups, GroupTeams)
    db.query(TournamentMatch).filter_by(tournament_id=tournament_id).delete()
    old_groups = db.query(TournamentGroup).filter_by(tournament_id=tournament_id).all()
    group_ids = [g.id for g in old_groups]
    if group_ids:
        db.query(GroupTeam).filter(GroupTeam.group_id.in_(group_ids)).delete(synchronize_session=False)
    db.query(TournamentGroup).filter_by(tournament_id=tournament_id).delete()
    db.commit()

    # 2. GENERATE FIXTURES
    if tournament.format in ["league", "hybrid"]:
        groups = create_groups(db, tournament_id, teams, group_count)

        for g in groups:
            group_teams = db.query(GroupTeam).filter_by(group_id=g.id).all()
            team_ids = [gt.team_id for gt in group_teams]

            # Formula: Team A vs Team B
            fixtures = paired_rounds(team_ids)

            def create_match_entry(
                    a_id,
                    b_id,
                    round_num
            ):

                ####################################################
                # CREATE REAL MATCH
                ####################################################

                match = models.Match(

                    id=generate_uuid(),

                    tournament_id=tournament_id,

                    team_a_id=a_id,

                    team_b_id=b_id,

                    total_overs=tournament.overs,

                    status="scheduled"
                )

                db.add(match)

                db.flush()

                ####################################################
                # CREATE FIXTURE
                ####################################################

                tm = TournamentMatch(

                    id=generate_uuid(),

                    tournament_id=tournament_id,

                    match_id=match.id,

                    team_a_id=a_id,

                    team_b_id=b_id,

                    team_a=db.query(Team).get(a_id).name,

                    team_b=db.query(Team).get(b_id).name,

                    match_type="league",

                    group_id=g.id,

                    round=round_num
                )

                db.add(tm)

            # First Round (A vs B)
            for a, b in fixtures:
                create_match_entry(a, b, 1)

            # 🔥 DOUBLE ROUND ROBIN LOGIC: Second Round (B vs A)
            if is_double_round:
                for a, b in fixtures:
                    # We swap a and b so Team B is now Team A (Home/Away logic)
                    create_match_entry(b, a, 2)

    db.commit()

    # 3. SCHEDULING LOGIC (Same as before)
    matches = db.query(TournamentMatch).filter_by(tournament_id=tournament_id).all()
    duration = get_match_duration(tournament.overs)
    current_time = datetime.strptime(start_time, "%H:%M")

    # Interleave matches from different groups to keep schedule interesting
    grouped = {}
    for m in matches:
        grouped.setdefault(m.group_id, []).append(m)

    order = []
    if grouped:
        max_len = max(len(v) for v in grouped.values())
        for i in range(max_len):
            for g_id in grouped:
                if i < len(grouped[g_id]):
                    order.append(grouped[g_id][i])

    for m in order:
        m.match_time = current_time.strftime("%H:%M")
        current_time += timedelta(minutes=duration + gap)

    db.commit()
    return {"message": f"Fixtures created. Total matches: {len(order)}"}


@router.get("/{tournament_id}/points")
def get_points(tournament_id: str, db: Session = Depends(get_db)):
    # ✅ Get all teams in tournament
    teams = db.query(TournamentTeam).filter_by(
        tournament_id=tournament_id,
        status="approved"
    ).all()

    result = []

    for t in teams:
        team_name = t.team.name
        team_id = t.team.id

        # ✅ Try to get points row
        p = db.query(TournamentPoints).filter_by(
            tournament_id=tournament_id,
            team_id=team_id
        ).first()

        if p:
            played = p.played
            wins = p.wins
            losses = p.losses
            points = p.points

            # NRR calc
            def convert_overs(overs):
                if overs is None:
                    return 0
                whole = int(overs)
                balls = int(round((overs - whole) * 10))
                return whole + (balls / 6)

            overs_faced = convert_overs(p.overs_faced)
            overs_bowled = convert_overs(p.overs_bowled)

            nrr = 0
            if overs_faced > 0 and overs_bowled > 0:
                nrr = (p.runs_scored / overs_faced) - (p.runs_conceded / overs_bowled)

        else:
            # ✅ DEFAULT VALUES
            played = 0
            wins = 0
            losses = 0
            points = 0
            nrr = 0

        result.append({
            "team": team_name,
            "played": played,
            "wins": wins,
            "losses": losses,
            "points": points,
            "nrr": round(nrr, 3)
        })

    # ✅ Sort
    result.sort(
        key=lambda x: (x["points"], x["nrr"], x["wins"]),
        reverse=True
    )

    return result


@router.post("/{tournament_id}/generate_knockouts")
def generate_knockouts(tournament_id: str, db: Session = Depends(get_db)):
    points = get_points(tournament_id, db)

    top4 = points[:4]

    semi1 = TournamentMatch(
        tournament_id=tournament_id,
        team_a=top4[0]["team"],
        team_b=top4[3]["team"],
        match_type="semi"
    )

    semi2 = TournamentMatch(
        tournament_id=tournament_id,
        team_a=top4[1]["team"],
        team_b=top4[2]["team"],
        match_type="semi"
    )

    db.add_all([semi1, semi2])
    db.commit()

    return {"message": "Semis created"}


@router.delete("/{tournament_id}/fixtures/upcoming")
def delete_upcoming_fixtures(
        tournament_id: str,
        db: Session = Depends(get_db),
        user_id: str = Depends(get_current_user_id)
):
    # 1. Authorization
    require_admin(db, user_id, tournament_id)

    # 2. Identify fixtures to be reset (where there is no winner yet)
    fixtures = db.query(models.TournamentMatch).filter(
        models.TournamentMatch.tournament_id == tournament_id,
        models.TournamentMatch.winner == None
    ).all()

    for f in fixtures:
        if f.match_id:
            # 🔥 CRITICAL FIX: Delete child records BEFORE deleting the Match
            # Order matters: Delete Balls -> Batsmen/Bowlers -> Match
            db.query(models.Ball).filter(models.Ball.match_id == f.match_id).delete()
            db.query(models.Batsman).filter(models.Batsman.match_id == f.match_id).delete()
            db.query(models.Bowler).filter(models.Bowler.match_id == f.match_id).delete()

            # Now safe to delete the main match scoring record
            db.query(models.Match).filter(models.Match.id == f.match_id).delete()

    # 3. Finally, delete the fixtures (TournamentMatch entries)
    deleted_count = db.query(models.TournamentMatch).filter(
        models.TournamentMatch.tournament_id == tournament_id,
        models.TournamentMatch.winner == None
    ).delete(synchronize_session=False)

    db.commit()

    return {
        "message": "Reset successful. All pending matches and scoring data cleared.",
        "deleted_fixtures": deleted_count
    }


@router.get("/{tournament_id}/teams")
def get_teams(
        tournament_id: str,
        db: Session = Depends(get_db)
):
    ########################################################
    # TOURNAMENT TEAMS
    ########################################################

    teams = db.query(TournamentTeam).filter(
        TournamentTeam.tournament_id == tournament_id,
        TournamentTeam.status == "approved"
    ).all()

    result = []

    ########################################################
    # LOOP
    ########################################################

    for t in teams:

        ####################################################
        # TEAM
        ####################################################

        team = db.query(Team).filter(
            Team.id == t.team_id
        ).first()

        if not team:
            continue

        ####################################################
        # GROUP
        ####################################################

        group_map = db.query(GroupTeam).join(
            TournamentGroup,
            GroupTeam.group_id == TournamentGroup.id
        ).filter(
            GroupTeam.team_id == t.team_id,
            TournamentGroup.tournament_id == tournament_id
        ).first()

        group_name = "No Group"

        if group_map:

            group = db.query(TournamentGroup).filter(
                TournamentGroup.id == group_map.group_id
            ).first()

            if group:
                group_name = group.name

        ####################################################
        # ENSURE POINTS ROW EXISTS
        ####################################################

        existing = db.query(TournamentPoints).filter(
            TournamentPoints.tournament_id == tournament_id,
            TournamentPoints.team_id == t.team_id
        ).first()

        if not existing:
            db.add(
                TournamentPoints(
                    id=generate_uuid(),

                    tournament_id=tournament_id,

                    team_id=t.team_id,

                    played=0,
                    wins=0,
                    losses=0,
                    points=0,

                    runs_scored=0,
                    runs_conceded=0,

                    overs_faced=0,
                    overs_bowled=0
                )
            )

        ####################################################
        # RESPONSE
        ####################################################

        result.append({
            "team_id": t.team_id,

            "team_name": team.name,

            "group_name": group_name
        })

    ########################################################
    # COMMIT
    ########################################################

    db.commit()

    return result


@router.delete("/teams/{team_id}")
def delete_team(
        team_id: str,
        db: Session = Depends(get_db)
):
    ####################################################
    # REMOVE TOURNAMENT LINKS
    ####################################################

    db.query(TournamentTeam).filter(
        TournamentTeam.team_id == team_id
    ).delete(synchronize_session=False)

    ####################################################
    # REMOVE GROUP LINKS
    ####################################################

    db.query(GroupTeam).filter(
        GroupTeam.team_id == team_id
    ).delete(synchronize_session=False)

    ####################################################
    # REMOVE FIXTURES
    ####################################################

    db.query(TournamentMatch).filter(
        (TournamentMatch.team_a_id == team_id) |
        (TournamentMatch.team_b_id == team_id)
    ).delete(synchronize_session=False)

    ####################################################
    # REMOVE INVITES
    ####################################################

    db.query(TeamInvite).filter(
        TeamInvite.team_id == team_id
    ).delete(synchronize_session=False)

    ####################################################
    # REMOVE PLAYERS
    ####################################################

    db.query(TeamPlayer).filter(
        TeamPlayer.team_id == team_id
    ).delete(synchronize_session=False)

    ####################################################
    # DELETE TEAM ONLY IF SAFE
    ####################################################

    remaining = db.query(TournamentTeam).filter(
        TournamentTeam.team_id == team_id
    ).count()

    if remaining == 0:
        db.query(Team).filter(
            Team.id == team_id
        ).delete(synchronize_session=False)

    db.commit()

    return {
        "success": True,
        "message": "Team removed"
    }


@router.post("/{tournament_id}/teams")
def add_team_to_tournament(
        tournament_id: str,
        body: dict,
        db: Session = Depends(get_db)
):
    ########################################################
    # VALIDATE
    ########################################################

    tournament = db.query(models.Tournament).filter(
        models.Tournament.id == tournament_id
    ).first()

    if not tournament:
        raise HTTPException(
            status_code=404,
            detail="Tournament not found"
        )

    ########################################################
    # TEAM NAME
    ########################################################

    name = body.get("name")

    if not name:
        raise HTTPException(
            status_code=400,
            detail="Team name required"
        )

    ########################################################
    # DUPLICATE CHECK
    ########################################################

    existing = db.query(models.Team).filter(
        models.Team.name.ilike(name)
    ).first()

    if existing:

        already = db.query(
            models.TournamentTeam
        ).filter(
            models.TournamentTeam.tournament_id
            == tournament_id,

            models.TournamentTeam.team_id
            == existing.id
        ).first()

        if already:
            raise HTTPException(
                status_code=400,
                detail="Team already added"
            )

        team = existing

    else:

        ####################################################
        # CREATE TEAM
        ####################################################

        team = models.Team(
            id=generate_uuid(),
            name=name
        )

        db.add(team)

        db.flush()

    ########################################################
    # LINK TO TOURNAMENT
    ########################################################

    link = models.TournamentTeam(
        id=generate_uuid(),
        tournament_id=tournament_id,
        team_id=team.id
    )

    db.add(link)

    db.commit()

    ########################################################
    # RESPONSE
    ########################################################

    return {
        "success": True,

        "team_id": team.id,

        "team_name": team.name,

        "tournament_id": tournament_id
    }


@router.post("/{tournament_id}/join")
def join_tournament(
        tournament_id: str,
        team_id: str,
        db: Session = Depends(get_db),
        user_id: str = Depends(get_current_user_id)
):
    # 🔥 BLOCK ADMIN
    admin = db.query(TournamentUser).filter_by(
        tournament_id=tournament_id,
        user_id=user_id,
        role="ADMIN"
    ).first()

    if admin:
        raise HTTPException(403, "Admin cannot join own tournament")

    # 🔥 CHECK TEAM OWNERSHIP
    team = db.query(Team).filter_by(id=team_id).first()

    if not team:
        raise HTTPException(404, "Team not found")

    if team.captain_id != user_id:
        raise HTTPException(403, "You can only join with your team")

    # ✅ TEAM FULL CHECK
    players_count = db.query(TeamPlayer).filter_by(team_id=team_id).count()
    max_players = team.max_players if hasattr(team, "max_players") else 11

    if players_count >= max_players:
        raise HTTPException(400, "Team is already full")

    # 🔥 CHECK EXISTING
    existing = db.query(TournamentTeam).filter_by(
        tournament_id=tournament_id,
        team_id=team_id
    ).first()

    if existing:
        if existing.status == "rejected":
            raise HTTPException(400, "Request was rejected")
        raise HTTPException(400, "Already joined")

    # 🔥 CREATE ENTRY
    entry = TournamentTeam(
        tournament_id=tournament_id,
        team_id=team_id,
        status="pending"
    )

    db.add(entry)
    db.commit()

    return {
        "success": True,
        "message": "Request sent"
    }


@router.post("/{tournament_id}/approve/{team_id}")
def approve_team(
        tournament_id: str,
        team_id: str,
        db: Session = Depends(get_db),
        user_id: str = Depends(get_current_user_id)
):
    require_admin(db, user_id, tournament_id)

    entry = db.query(TournamentTeam).filter_by(
        tournament_id=tournament_id,
        team_id=team_id
    ).first()

    if not entry:
        raise HTTPException(404, "Not found")

    if entry.status == "approved":
        raise HTTPException(400, "Already approved")

    entry.status = "approved"
    db.commit()

    return {"message": "Approved"}


@router.get("/{tournament_id}/request")
def get_requests(
        tournament_id: str,
        db: Session = Depends(get_db),
        user_id: str = Depends(get_current_user_id)
):
    require_admin(db, user_id, tournament_id)

    teams = db.query(TournamentTeam).filter_by(
        tournament_id=tournament_id,
        status="pending"
    ).all()

    return [
        {
            "team_id": t.team.id,
            "team_name": t.team.name,
            # Pass the contact info if you have it in your DB,
            # otherwise pass a placeholder or the captain's phone number
            "contact": getattr(t, 'contact', '')
        }
        for t in teams
    ]


@router.post("/join_request")
def create_join_request(
        req: JoinRequestPayload,
        db: Session = Depends(get_db),
        user_id: str = Depends(get_current_user_id)
):
    # Step A: Create the Team in the database
    new_team = Team(
        id=str(uuid.uuid4()),
        name=req.team_name,
        captain_id=user_id
    )
    db.add(new_team)
    db.flush()  # Flush generates the ID without fully committing yet

    # Step B: Link the team to the tournament with a "pending" status
    new_request = TournamentTeam(
        tournament_id=req.tournament_id,
        team_id=new_team.id,
        status="pending"
        # Note: If your TournamentTeam model has a 'contact' column, add it here!
        # contact=req.contact
    )
    db.add(new_request)
    db.commit()

    return {"status": "success", "message": "Join request submitted!"}


@router.post("/{tournament_id}/reject/{team_id}")
def reject_team(
        tournament_id: str,
        team_id: str,
        db: Session = Depends(get_db),
        user_id: str = Depends(get_current_user_id)
):
    require_admin(db, user_id, tournament_id)

    entry = db.query(TournamentTeam).filter_by(
        tournament_id=tournament_id,
        team_id=team_id
    ).first()

    if not entry:
        raise HTTPException(404, "Not found")

    if entry.status == "rejected":
        raise HTTPException(400, "Already rejected")

    entry.status = "rejected"
    db.commit()

    return {"message": "Rejected"}


@router.post("/{tournament_id}/next_round")
def next_round(tournament_id: str, db: Session = Depends(get_db)):
    points = db.query(TournamentPoints).filter_by(
        tournament_id=tournament_id
    ).all()

    sorted_teams = sorted(
        points,
        key=lambda x: (x.points, x.runs_scored),
        reverse=True
    )

    top4 = sorted_teams[:4]

    fixtures = generate_knockout([t.team_name for t in top4])

    for a, b in fixtures:
        db.add(TournamentMatch(
            tournament_id=tournament_id,
            team_a=a,
            team_b=b,
            match_type="knockout",
            round=2
        ))

    db.commit()

    return {"message": "Next round created"}


@router.get("/{tournament_id}/matches")
def get_matches(
        tournament_id: str,
        db: Session = Depends(get_db)
):
    ########################################################
    # LOAD TOURNAMENT FIXTURES
    ########################################################
    matches = db.query(TournamentMatch).filter_by(
        tournament_id=tournament_id
    ).all()

    result = []

    ########################################################
    # LOOP THROUGH FIXTURES
    ########################################################
    for m in matches:

        ####################################################
        # TEAM DETAILS
        ####################################################
        teamA = db.query(Team).get(m.team_a_id) if m.team_a_id else None
        teamB = db.query(Team).get(m.team_b_id) if m.team_b_id else None

        ####################################################
        # LINKED MATCH (REAL SCORING MATCH)
        ####################################################
        match = None

        if m.match_id:
            match = db.query(models.Match).filter(
                models.Match.id == m.match_id
            ).first()

        ####################################################
        # RESPONSE
        ####################################################
        result.append({
            # Fixture ID
            "id": m.id,

            # Linked Match ID used for scoring
            "match_id": m.match_id,

            # Team IDs
            "team_a_id": m.team_a_id,
            "team_b_id": m.team_b_id,

            # Team Names
            "team_a": teamA.name if teamA else "TBD",
            "team_b": teamB.name if teamB else "TBD",

            # Fixture Info
            "match_type": m.match_type,
            "group_id": m.group_id,
            "match_time": m.match_time,

            # Winner stored in TournamentMatch
            "winner": m.winner,

            # 🔥 CRITICAL FIELDS FOR FLUTTER UI
            "status": match.status if match else "scheduled",
            "result": match.result if match else None,
            "final_score": (
                getattr(match, "final_score", None)
                if match else None
            ),

            # Optional Extras
            "target": (
                getattr(match, "target", None)
                if match else None
            ),
            "current_innings": (
                getattr(match, "current_innings", None)
                if match else None
            ),

            # Compatibility field
            "is_live": (
                match.status == "live"
                if match and match.status
                else False
            ),
        })

    ########################################################
    # RETURN ALL FIXTURES
    ########################################################
    return result


@router.post("/teams/{team_id}/invite")
def create_invite(team_id: str, db: Session = Depends(get_db)):
    code = str(uuid.uuid4())[:8]

    invite = TeamInvite(
        team_id=team_id,
        code=code
    )

    db.add(invite)
    db.commit()

    return {
        "code": code,
        "link": f"https://runbhoomi.app/join-team/{code}"
    }


@router.post("/teams/join/{code}")
def join_team_by_code(code: str, player_id: str, db: Session = Depends(get_db)):
    # 1. Look up the invite code in the database
    invite = db.query(TeamInvite).filter(TeamInvite.code == code).first()

    if not invite:
        raise HTTPException(status_code=404, detail="Invalid or expired invite code")

    # 2. Check if the player exists
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    # 3. Check if the player is already in the team to avoid duplicates
    existing_member = db.query(TeamPlayer).filter(
        TeamPlayer.team_id == invite.team_id,
        TeamPlayer.player_id == player_id
    ).first()

    if existing_member:
        return {"message": "You are already a member of this team", "team_id": invite.team_id}

    # 4. Create the new team membership
    new_member = TeamPlayer(
        team_id=invite.team_id,
        player_id=player_id,
        role="Player"  # Default role when joining via code
    )

    db.add(new_member)
    db.commit()
    db.refresh(new_member)

    return {
        "status": "success",
        "message": "Successfully joined the team",
        "team_id": invite.team_id
    }


@router.get("/{tournament_id}/groups")
def get_groups(tournament_id: str, db: Session = Depends(get_db)):
    groups = db.query(TournamentGroup).filter_by(
        tournament_id=tournament_id
    ).all()

    return [
        {"id": g.id, "name": g.name}
        for g in groups
    ]


@router.put("/teams/{team_id}/group")
def update_team_group(team_id: str, payload: GroupUpdateRequest, db: Session = Depends(get_db)):
    """
    Updates a team's group using the GroupTeam mapping table.
    """
    # 1. Find the team
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # 2. Find which tournament this team belongs to
    # (Assuming the team is only in one active tournament for this context)
    tournament_link = db.query(TournamentTeam).filter(TournamentTeam.team_id == team_id).first()
    if not tournament_link:
        raise HTTPException(status_code=400, detail="Team is not registered in any tournament")

    tournament_id = tournament_link.tournament_id

    # 3. Remove the team's current group assignment for this tournament
    old_mappings = db.query(GroupTeam).join(
        TournamentGroup, GroupTeam.group_id == TournamentGroup.id
    ).filter(
        GroupTeam.team_id == team_id,
        TournamentGroup.tournament_id == tournament_id
    ).all()

    for old in old_mappings:
        db.delete(old)

    db.flush()  # Execute deletes before adding new ones

    # 4. Handle un-assigning (moving back to "No Group")
    if payload.group_name == "No Group":
        db.commit()
        return {"status": "success", "message": "Team removed from group"}

    # 5. Find or Create the Group in the TournamentGroup table
    group = db.query(TournamentGroup).filter(
        TournamentGroup.tournament_id == tournament_id,
        TournamentGroup.name == payload.group_name
    ).first()

    if not group:
        # The admin typed a Custom Group that doesn't exist yet! Let's create it.
        group = TournamentGroup(
            tournament_id=tournament_id,
            name=payload.group_name
        )
        db.add(group)
        db.flush()  # Generate the group.id immediately

    # 6. Link the team to the group using the GroupTeam mapping table
    new_mapping = GroupTeam(
        group_id=group.id,
        team_id=team.id
    )
    db.add(new_mapping)
    db.commit()

    return {"status": "success", "message": f"Team moved to {group.name}"}


@router.get("/{tournament_id}/my-role")
def get_my_role(
        tournament_id: str,
        db: Session = Depends(get_db),
        user_id: str = Depends(get_current_user_id)
):
    record = db.query(TournamentUser).filter_by(
        tournament_id=tournament_id,
        user_id=user_id
    ).first()

    if not record:
        return {"role": "PLAYER"}

    return {"role": record.role}


@router.get("/users/search", response_model=UserSearchResponse)
async def search_user_by_phone(phone: str, db: Session = Depends(get_db)):
    # 🔥 CHANGE: Search the Player table
    user = db.query(Player).filter(Player.phone == phone).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found with this mobile number")

    return {
        "id": user.id,
        "name": user.name,
        "phone": user.phone
    }


@router.get("/{tournament_id}/officials")
async def get_tournament_officials(tournament_id: str, db: Session = Depends(get_db)):
    """
    Fetches all officials assigned to a specific tournament.
    """
    officials = db.query(TournamentOfficial).filter(
        TournamentOfficial.tournament_id == tournament_id
    ).all()

    response_data = []
    for off in officials:
        response_data.append({
            "id": off.user_id,
            "name": off.user.name,  # Eagerly loaded from Player table
            "phone": off.user.phone,
            "role": off.role
        })

    return response_data


@router.post("/{tournament_id}/officials")
async def assign_tournament_official(
        tournament_id: str,
        official: OfficialAssignRequest,
        db: Session = Depends(get_db)
):
    """
    Assigns a user as a Scorer or Umpire to a tournament.
    """
    # 1. Verify the user actually exists in the global users table
    user = db.query(Player).filter(Player.id == official.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found in the system")

    # 2. Prevent duplicates (Don't let the same user be added twice to the same tournament)
    existing_official = db.query(TournamentOfficial).filter(
        TournamentOfficial.tournament_id == tournament_id,
        TournamentOfficial.user_id == official.id
    ).first()

    if existing_official:
        raise HTTPException(status_code=400, detail=f"User is already assigned as {existing_official.role}")

    # 3. Create the new official record
    new_official = TournamentOfficial(
        tournament_id=tournament_id,
        user_id=official.id,
        role=official.role.upper()  # Ensure role is always uppercase (SCORER/UMPIRE)
    )

    db.add(new_official)
    db.commit()

    return {"message": "Official assigned successfully", "status": "success"}


@router.delete("/{tournament_id}/officials/{user_id}")
async def remove_tournament_official(
        tournament_id: str,
        user_id: int,
        db: Session = Depends(get_db)
):
    """
    Removes an official from a tournament.
    """
    # Find the specific mapping record
    record = db.query(TournamentOfficial).filter(
        TournamentOfficial.tournament_id == tournament_id,
        TournamentOfficial.user_id == user_id
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail="Official record not found")

    # Delete and commit
    db.delete(record)
    db.commit()

    return {"message": "Official removed successfully", "status": "success"}


@router.patch("/teams/{team_id}/players/{player_id}/details")
def update_player_details(
        team_id: str,
        player_id: str,
        payload: dict,
        db: Session = Depends(get_db),
        current_user_id: str = Depends(get_current_user_id)
):
    # 1. Get the target player
    player_entry = db.query(models.TeamPlayer).filter(
        models.TeamPlayer.team_id == team_id,
        models.TeamPlayer.player_id == player_id
    ).first()

    if not player_entry:
        raise HTTPException(status_code=404, detail="Player not found in this team")

    # --- NEW: GLOBAL RESET LOGIC ---
    # If this player is becoming Captain, remove Captain status from all others in the team
    if payload.get("is_captain") is True:
        db.query(models.TeamPlayer).filter(
            models.TeamPlayer.team_id == team_id,
            models.TeamPlayer.player_id != player_id
        ).update({models.TeamPlayer.is_captain: False})

    # If this player is becoming VC, remove VC status from all others
    if payload.get("is_vc") is True:
        db.query(models.TeamPlayer).filter(
            models.TeamPlayer.team_id == team_id,
            models.TeamPlayer.player_id != player_id
        ).update({models.TeamPlayer.is_vc: False})

    # If your business logic only allows ONE Admin per team:
    if str(payload.get("role")).upper() == "ADMIN":
        db.query(models.TeamPlayer).filter(
            models.TeamPlayer.team_id == team_id,
            models.TeamPlayer.player_id != player_id
        ).update({models.TeamPlayer.role: "PLAYER"})
    # -------------------------------

    # 2. Update Target Player Fields
    if "player_type" in payload:
        player_entry.player_type = payload.get("player_type")

    if "is_captain" in payload:
        player_entry.is_captain = bool(payload.get("is_captain"))

    if "is_vc" in payload:
        player_entry.is_vc = bool(payload.get("is_vc"))

    if "is_wk" in payload:
        player_entry.is_wk = bool(payload.get("is_wk"))

    if "role" in payload:
        player_entry.role = str(payload.get("role")).upper()

    try:
        db.commit()
        db.refresh(player_entry)
        return {
            "status": "success",
            "message": "Player roles updated and previous holders demoted",
            "data": {
                "role": player_entry.role,
                "is_captain": player_entry.is_captain,
                "is_vc": player_entry.is_vc
            }
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/teams/{team_id}/players/{player_id}/role")
def update_player_role(
        team_id: str,
        player_id: str,
        payload: RoleUpdate,
        db: Session = Depends(get_db),
        current_user_id: str = Depends(get_current_user_id)
):
    # Verify the player is in the team
    player_entry = db.query(models.TeamPlayer).filter(
        models.TeamPlayer.team_id == team_id,
        models.TeamPlayer.player_id == player_id
    ).first()

    if not player_entry:
        raise HTTPException(status_code=404, detail="Player not found in this team")

    player_entry.role = payload.role.upper()  # Store as ADMIN or CAPTAIN
    db.commit()
    return {"message": f"Role updated to {payload.role}"}


# 2. REMOVE PLAYER (Endpoint: /tournaments/teams/{team_id}/players/{player_id})
@router.delete("/teams/{team_id}/players/{player_id}")
def remove_player_from_team(
        team_id: str,
        player_id: str,
        db: Session = Depends(get_db),
        current_user_id: str = Depends(get_current_user_id)
):
    player_entry = db.query(models.TeamPlayer).filter(
        models.TeamPlayer.team_id == team_id,
        models.TeamPlayer.player_id == player_id
    ).first()

    if not player_entry:
        raise HTTPException(status_code=404, detail="Player entry not found")

    db.delete(player_entry)
    db.commit()
    return {"message": "Player removed successfully"}


def check_tournament_admin_privileges(tournament_id: str, current_user_id: str, db: Session):
    """
    CricHeroes Authorization Logic:
    Validates if the requesting user is either the original Super Admin creator
    or an explicitly designated Co-Admin via the relationship table.
    """
    tournament = db.query(models.Tournament).filter(models.Tournament.id == tournament_id).first()
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament container not found")

    # Check if the player exists in the explicit tournament_admins mapping table
    is_co_admin = db.query(models.TournamentAdmin).filter(
        models.TournamentAdmin.tournament_id == tournament_id,
        models.TournamentAdmin.player_id == current_user_id
    ).first()

    # Deny access if they aren't the original owner and aren't in the co-admins list
    if tournament.created_by != current_user_id and not is_co_admin:
        raise HTTPException(
            status_code=403,
            detail="Access Denied: You do not possess administrative rights for this tournament."
        )

    return tournament


@router.get("/{tournament_id}")
def get_tournament_details(
        tournament_id: str,
        db: Session = Depends(get_db)
):
    tournament = db.query(models.Tournament).filter(models.Tournament.id == tournament_id).first()
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")

    # Return the tournament data including the co-admins relationship
    # return {
    #     "id": tournament.id,
    #     "name": tournament.name,
    #     "created_by": tournament.created_by,
    #     "co_admins": [{"player": {"id": ca.player.id, "name": ca.player.name}} for ca in tournament.co_admins]
    # }
    return {
        "id": tournament.id,
        "name": tournament.name,

        "city": tournament.city,
        "ground": tournament.ground,
        "address": tournament.address,

        "latitude": tournament.latitude,
        "longitude": tournament.longitude,

        "match_type": tournament.match_type,

        "total_teams": tournament.total_teams,

        "format": tournament.format,
        "overs": tournament.overs,

        "start_date": tournament.start_date,
        "end_date": tournament.end_date,

        "banner_url": tournament.banner_url,
        "logo_url": tournament.logo_url,

        "created_by": tournament.created_by,

        "co_admins": [
            {
                "player": {
                    "id": ca.player.id,
                    "name": ca.player.name
                }
            }
            for ca in tournament.co_admins
        ]
    }
