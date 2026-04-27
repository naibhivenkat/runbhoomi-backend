import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi import Query
from pydantic import BaseModel
from sqlalchemy import cast, Time
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user_id
from app.database import models
from app.database.db import get_db
from app.database.models import TournamentTeam, TournamentPoints, TournamentMatch, Team, GroupTeam, TeamInvite, \
    TeamPlayer, TournamentGroup, TournamentUser
from app.tournaments.group_service import create_groups, generate_knockout, paired_rounds, \
    get_match_duration
from app.utls.permissions import require_admin

router = APIRouter(prefix="/tournaments")

class JoinRequestPayload(BaseModel):
    tournament_id: str
    team_name: str
    contact: str
    status: str = "PENDING"


class TournamentCreate(BaseModel):
    name: str
    city: str
    ground: str

    organizer_name: str
    organizer_phone: str
    organizer_email: str

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


@router.post("/create")
def create_tournament(
        data: dict,
        db: Session = Depends(get_db),
        user_id: str = Depends(get_current_user_id)
):
    tournament = models.Tournament(
        name=data.get("name"),
        city=data.get("city"),
        ground=data.get("ground"),

        organizer_name=data.get("organizer_name"),
        organizer_phone=data.get("organizer_phone"),
        organizer_email=data.get("organizer_email"),

        start_date=data.get("start_date"),
        end_date=data.get("end_date"),

        category=data.get("category"),
        ball_type=data.get("ball_type"),
        pitch_type=data.get("pitch_type"),
        match_type=data.get("match_type"),

        total_teams=data.get("total_teams"),
        format=data.get("format"),
        overs=data.get("overs"),

        logo_url=data.get("logo_url"),
        banner_url=data.get("banner_url"),

        created_by=user_id
    )

    db.add(tournament)
    db.commit()
    db.refresh(tournament)

    # ADMIN ENTRY
    admin_entry = TournamentUser(
        tournament_id=tournament.id,
        user_id=user_id,
        role="ADMIN"
    )
    db.add(admin_entry)
    db.commit()

    return {
        "message": "Tournament created",
        "tournament_id": tournament.id
    }


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
        team_name=team.name
    ))

    db.commit()

    return {"message": "Team added"}


@router.get("/")
def get_tournaments(db: Session = Depends(get_db)):
    tournaments = db.query(models.Tournament).all()

    return [
        {
            "id": t.id,
            "name": t.name,
            "city": t.city,
            "ground": t.ground,
            "match_type": t.match_type,
            "total_teams": t.total_teams,
            "start_date": t.start_date,
            "end_date": t.end_date,
            "banner_url": getattr(t, "banner_url", None),
            "logo_url": getattr(t, "logo_url", None),
        }
        for t in tournaments
    ]


@router.post("/{tournament_id}/generate_fixtures")
def generate_fixtures(
        tournament_id: str,
        group_count: int = Query(2),
        start_time: str = Query("08:00"),
        gap: int = Query(10),
        db: Session = Depends(get_db),
        user_id: str = Depends(get_current_user_id)  # 🔥 ADD
):
    # 🔐 ADMIN CHECK (MOST IMPORTANT)
    require_admin(db, user_id, tournament_id)

    tournament = db.query(models.Tournament).get(tournament_id)

    if not tournament:
        raise HTTPException(404, "Tournament not found")

    teams = db.query(TournamentTeam).filter_by(
        tournament_id=tournament_id,
        status="approved"
    ).all()

    if len(teams) < 2:
        raise HTTPException(400, "Not enough teams")

    # DELETE OLD
    db.query(TournamentMatch).filter(
        TournamentMatch.tournament_id == tournament_id
    ).delete(synchronize_session=False)

    old_groups = db.query(TournamentGroup).filter(
        TournamentGroup.tournament_id == tournament_id
    ).all()

    group_ids = [g.id for g in old_groups]

    if group_ids:
        db.query(GroupTeam).filter(
            GroupTeam.group_id.in_(group_ids)
        ).delete(synchronize_session=False)

    db.query(TournamentGroup).filter(
        TournamentGroup.tournament_id == tournament_id
    ).delete(synchronize_session=False)

    db.commit()

    ids = [t.team_id for t in teams]

    matches_created = []

    if tournament.format in ["league", "hybrid"]:

        groups = create_groups(db, tournament_id, teams, group_count)

        for g in groups:
            group_teams = db.query(GroupTeam).filter_by(group_id=g.id).all()
            team_ids = [gt.team_id for gt in group_teams]

            fixtures = paired_rounds(team_ids)

            for a, b in fixtures:
                m = TournamentMatch(
                    tournament_id=tournament_id,
                    team_a_id=a,
                    team_b_id=b,
                    team_a=db.query(Team).get(a).name,
                    team_b=db.query(Team).get(b).name,
                    match_type="league",
                    group_id=g.id,
                    round=1
                )
                db.add(m)
                matches_created.append(m)

    db.commit()

    matches = db.query(TournamentMatch).filter_by(
        tournament_id=tournament_id
    ).order_by(cast(TournamentMatch.match_time, Time)).all()

    duration = get_match_duration(tournament.overs)
    current_time = datetime.strptime(start_time, "%H:%M")

    grouped = {}
    for m in matches:
        grouped.setdefault(m.group_id, []).append(m)

    order = []
    max_len = max(len(v) for v in grouped.values())

    for i in range(max_len):
        for g in grouped:
            if i < len(grouped[g]):
                order.append(grouped[g][i])

    for m in order:
        m.match_time = current_time.strftime("%H:%M")
        current_time += timedelta(minutes=duration + gap)

    db.commit()

    return {"message": "Fixtures created with schedule"}


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

        # ✅ Try to get points row
        p = db.query(TournamentPoints).filter_by(
            tournament_id=tournament_id,
            team_name=team_name
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
        stage="semi"
    )

    semi2 = TournamentMatch(
        tournament_id=tournament_id,
        team_a=top4[1]["team"],
        team_b=top4[2]["team"],
        stage="semi"
    )

    db.add_all([semi1, semi2])
    db.commit()

    return {"message": "Semis created"}


@router.delete("/{tournament_id}/fixtures/upcoming")
def delete_upcoming_fixtures(tournament_id: str, db: Session = Depends(get_db)):
    deleted = db.query(TournamentMatch).filter(
        TournamentMatch.tournament_id == tournament_id,
        TournamentMatch.match_id == None,
        TournamentMatch.winner == None
    ).delete(synchronize_session=False)

    db.commit()

    return {
        "message": "Upcoming fixtures deleted",
        "deleted": deleted
    }


@router.get("/{tournament_id}/teams")
def get_teams(tournament_id: str, db: Session = Depends(get_db)):
    teams = db.query(TournamentTeam).filter_by(
        tournament_id=tournament_id,
        status="approved"
    ).all()

    result = []

    for t in teams:
        team = db.query(Team).get(t.team_id)
        team_name = team.name if team else "Unknown"

        # 🔍 GROUP MAPPING
        group_map = db.query(GroupTeam).join(
            TournamentGroup,
            GroupTeam.group_id == TournamentGroup.id
        ).filter(
            GroupTeam.team_id == t.team_id,
            TournamentGroup.tournament_id == tournament_id
        ).first()

        group_name = None

        if group_map:
            group = db.query(TournamentGroup).get(group_map.group_id)
            if group:
                group_name = group.name

        # 🔥💥 ENSURE POINTS ROW EXISTS
        existing = db.query(TournamentPoints).filter_by(
            tournament_id=tournament_id,
            team_name=team_name
        ).first()

        if not existing:
            db.add(TournamentPoints(
                tournament_id=tournament_id,
                team_name=team_name,
                played=0,
                wins=0,
                losses=0,
                points=0,
                runs_scored=0,
                runs_conceded=0,
                overs_faced=0,
                overs_bowled=0
            ))

        result.append({
            "team_id": t.team_id,
            "team_name": team_name,
            "group_name": group_name or "No Group"
        })

    db.commit()

    return result


@router.delete("/teams/{team_id}")
def delete_team(team_id: str, db: Session = Depends(get_db)):
    # remove mapping
    db.query(TournamentTeam).filter(
        TournamentTeam.team_id == team_id
    ).delete(synchronize_session=False)

    # remove fixtures
    db.query(TournamentMatch).filter(
        (TournamentMatch.team_a_id == team_id) |
        (TournamentMatch.team_b_id == team_id)
    ).delete(synchronize_session=False)

    db.commit()

    return {"message": "Team removed"}


@router.post("/teams/create")
def create_team(name: str, captain_id: str, db: Session = Depends(get_db)):
    team = Team(name=name, captain_id=captain_id)

    db.add(team)
    db.commit()
    db.refresh(team)

    return {
        "id": team.id,
        "name": team.name,
        "captain_id": team.captain_id
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


@router.get("/{tournament_id}/join_request")
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


@router.get("/{tournament_id}/requests")
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
    db.flush() # Flush generates the ID without fully committing yet

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
def get_matches(tournament_id: str, db: Session = Depends(get_db)):
    matches = db.query(TournamentMatch).filter_by(
        tournament_id=tournament_id
    ).all()

    result = []

    for m in matches:
        teamA = db.query(Team).get(m.team_a_id) if m.team_a_id else None
        teamB = db.query(Team).get(m.team_b_id) if m.team_b_id else None

        result.append({
            "id": m.id,
            "team_a_id": m.team_a_id,
            "team_b_id": m.team_b_id,

            "team_a": teamA.name if teamA else "TBD",
            "team_b": teamB.name if teamB else "TBD",

            "stage": m.match_type,
            "winner": m.winner,

            "group_id": m.group_id,
            "match_time": m.match_time,

            "is_live": False,
        })

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
    invite = db.query(TeamInvite).filter_by(code=code).first()

    if not invite:
        raise HTTPException(404, "Invalid code")

    db.add(TeamPlayer(
        team_id=invite.team_id,
        player_id=player_id
    ))

    db.commit()

    return {"message": "Joined team"}


@router.get("/{tournament_id}/groups")
def get_groups(tournament_id: str, db: Session = Depends(get_db)):
    groups = db.query(TournamentGroup).filter_by(
        tournament_id=tournament_id
    ).all()

    return [
        {"id": g.id, "name": g.name}
        for g in groups
    ]


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












# import uuid
# from datetime import datetime, timedelta
#
# from fastapi import APIRouter, Depends, HTTPException
# from fastapi import Query
# from pydantic import BaseModel
# from sqlalchemy import cast, Time
# from sqlalchemy.orm import Session
#
# from app.auth.deps import get_current_user_id
# from app.database import models
# from app.database.db import get_db
# from app.database.models import TournamentTeam, TournamentPoints, TournamentMatch, Team, GroupTeam, TeamInvite, \
#     TeamPlayer, TournamentGroup, TournamentUser
# from app.tournaments.group_service import create_groups, generate_knockout, paired_rounds, \
#     get_match_duration
# from app.utls.permissions import require_admin
#
# router = APIRouter(prefix="/tournaments")
#
#
# class TournamentCreate(BaseModel):
#     name: str
#     city: str
#     ground: str
#
#     organizer_name: str
#     organizer_phone: str
#     organizer_email: str
#
#     start_date: str
#     end_date: str
#
#     category: str
#     ball_type: str
#     pitch_type: str
#     match_type: str
#
#     total_teams: int
#
#     format: str = "league"
#     overs: int = 20
#
#     logo_url: str | None = None
#     banner_url: str | None = None
#
#
# @router.post("/create")
# def create_tournament(
#         data: dict,
#         db: Session = Depends(get_db),
#         user_id: int = Depends(get_current_user_id)
# ):
#     tournament = models.Tournament(
#         name=data.get("name"),
#         city=data.get("city"),
#         ground=data.get("ground"),
#
#         organizer_name=data.get("organizer_name"),
#         organizer_phone=data.get("organizer_phone"),
#         organizer_email=data.get("organizer_email"),
#
#         start_date=data.get("start_date"),
#         end_date=data.get("end_date"),
#
#         category=data.get("category"),
#         ball_type=data.get("ball_type"),
#         pitch_type=data.get("pitch_type"),
#         match_type=data.get("match_type"),
#
#         total_teams=data.get("total_teams"),
#         format=data.get("format"),
#         overs=data.get("overs"),
#
#         logo_url=data.get("logo_url"),
#         banner_url=data.get("banner_url"),
#
#         created_by=user_id
#     )
#
#     db.add(tournament)
#     db.commit()
#     db.refresh(tournament)
#
#     # ADMIN ENTRY
#     admin_entry = TournamentUser(
#         tournament_id=tournament.id,
#         user_id=user_id,
#         role="ADMIN"
#     )
#     db.add(admin_entry)
#     db.commit()
#
#     return {
#         "message": "Tournament created",
#         "tournament_id": tournament.id
#     }
#
#
# @router.post("/matches/{tm_id}/init")
# def init_match_from_fixture(tm_id: int, db: Session = Depends(get_db)):
#     tm = db.query(models.TournamentMatch).get(tm_id)
#
#     if not tm:
#         raise HTTPException(404, "Fixture not found")
#
#     # already created
#     if tm.match_id:
#         return {"match_id": tm.match_id}
#
#     # ✅ FIX: USE REAL TEAM IDs
#     match = models.Match(
#         team_a_id=tm.team_a_id,
#         team_b_id=tm.team_b_id,
#         status="created"
#     )
#
#     db.add(match)
#     db.commit()
#     db.refresh(match)
#
#     tm.match_id = match.id
#     db.commit()
#
#     return {"match_id": match.id}
#
#
# @router.post("/{tournament_id}/add_team")
# def add_team(tournament_id: int, team_name: str, db: Session = Depends(get_db)):
#     tournament = db.query(models.Tournament).filter_by(id=tournament_id).first()
#
#     if not tournament:
#         raise HTTPException(404, "Tournament not found")
#
#     # create or get team
#     team = db.query(Team).filter_by(name=team_name).first()
#
#     if not team:
#         team = Team(name=team_name)
#         db.add(team)
#         db.commit()
#         db.refresh(team)
#
#     # check duplicate
#     existing = db.query(TournamentTeam).filter_by(
#         tournament_id=tournament_id,
#         team_id=team.id
#     ).first()
#
#     if existing:
#         raise HTTPException(400, "Team already exists")
#
#     # max teams check
#     count = db.query(TournamentTeam).filter_by(
#         tournament_id=tournament_id
#     ).count()
#
#     if count >= tournament.total_teams:
#         raise HTTPException(400, "Max teams reached")
#
#     entry = TournamentTeam(
#         tournament_id=tournament_id,
#         team_id=team.id,
#         status="approved"  # ✅ FIX
#     )
#
#     db.add(entry)
#
#     db.add(TournamentPoints(
#         tournament_id=tournament_id,
#         team_name=team.name
#     ))
#
#     db.commit()
#
#     return {"message": "Team added"}
#
#
# @router.get("/")
# def get_tournaments(db: Session = Depends(get_db)):
#     tournaments = db.query(models.Tournament).all()
#
#     return [
#         {
#             "id": t.id,
#             "name": t.name,
#             "city": t.city,
#             "ground": t.ground,
#             "match_type": t.match_type,
#             "total_teams": t.total_teams,
#             "start_date": t.start_date,
#             "end_date": t.end_date,
#             "banner_url": getattr(t, "banner_url", None),
#             "logo_url": getattr(t, "logo_url", None),
#         }
#         for t in tournaments
#     ]
#
#
# @router.post("/{tournament_id}/generate_fixtures")
# def generate_fixtures(
#         tournament_id: int,
#         group_count: int = Query(2),
#         start_time: str = Query("08:00"),
#         gap: int = Query(10),
#         db: Session = Depends(get_db),
#         user_id: int = Depends(get_current_user_id)  # 🔥 ADD
# ):
#     # 🔐 ADMIN CHECK (MOST IMPORTANT)
#     require_admin(db, user_id, tournament_id)
#
#     tournament = db.query(models.Tournament).get(tournament_id)
#
#     if not tournament:
#         raise HTTPException(404, "Tournament not found")
#
#     teams = db.query(TournamentTeam).filter_by(
#         tournament_id=tournament_id,
#         status="approved"
#     ).all()
#
#     if len(teams) < 2:
#         raise HTTPException(400, "Not enough teams")
#
#     # DELETE OLD
#     db.query(TournamentMatch).filter(
#         TournamentMatch.tournament_id == tournament_id
#     ).delete(synchronize_session=False)
#
#     old_groups = db.query(TournamentGroup).filter(
#         TournamentGroup.tournament_id == tournament_id
#     ).all()
#
#     group_ids = [g.id for g in old_groups]
#
#     if group_ids:
#         db.query(GroupTeam).filter(
#             GroupTeam.group_id.in_(group_ids)
#         ).delete(synchronize_session=False)
#
#     db.query(TournamentGroup).filter(
#         TournamentGroup.tournament_id == tournament_id
#     ).delete(synchronize_session=False)
#
#     db.commit()
#
#     ids = [t.team_id for t in teams]
#
#     matches_created = []
#
#     if tournament.format in ["league", "hybrid"]:
#
#         groups = create_groups(db, tournament_id, teams, group_count)
#
#         for g in groups:
#             group_teams = db.query(GroupTeam).filter_by(group_id=g.id).all()
#             team_ids = [gt.team_id for gt in group_teams]
#
#             fixtures = paired_rounds(team_ids)
#
#             for a, b in fixtures:
#                 m = TournamentMatch(
#                     tournament_id=tournament_id,
#                     team_a_id=a,
#                     team_b_id=b,
#                     team_a=db.query(Team).get(a).name,
#                     team_b=db.query(Team).get(b).name,
#                     match_type="league",
#                     group_id=g.id,
#                     round=1
#                 )
#                 db.add(m)
#                 matches_created.append(m)
#
#     db.commit()
#
#     matches = db.query(TournamentMatch).filter_by(
#         tournament_id=tournament_id
#     ).order_by(cast(TournamentMatch.match_time, Time)).all()
#
#     duration = get_match_duration(tournament.overs)
#     current_time = datetime.strptime(start_time, "%H:%M")
#
#     grouped = {}
#     for m in matches:
#         grouped.setdefault(m.group_id, []).append(m)
#
#     order = []
#     max_len = max(len(v) for v in grouped.values())
#
#     for i in range(max_len):
#         for g in grouped:
#             if i < len(grouped[g]):
#                 order.append(grouped[g][i])
#
#     for m in order:
#         m.match_time = current_time.strftime("%H:%M")
#         current_time += timedelta(minutes=duration + gap)
#
#     db.commit()
#
#     return {"message": "Fixtures created with schedule"}
#
#
# @router.get("/{tournament_id}/points")
# def get_points(tournament_id: int, db: Session = Depends(get_db)):
#     # ✅ Get all teams in tournament
#     teams = db.query(TournamentTeam).filter_by(
#         tournament_id=tournament_id,
#         status="approved"
#     ).all()
#
#     result = []
#
#     for t in teams:
#         team_name = t.team.name
#
#         # ✅ Try to get points row
#         p = db.query(TournamentPoints).filter_by(
#             tournament_id=tournament_id,
#             team_name=team_name
#         ).first()
#
#         if p:
#             played = p.played
#             wins = p.wins
#             losses = p.losses
#             points = p.points
#
#             # NRR calc
#             def convert_overs(overs):
#                 if overs is None:
#                     return 0
#                 whole = int(overs)
#                 balls = int(round((overs - whole) * 10))
#                 return whole + (balls / 6)
#
#             overs_faced = convert_overs(p.overs_faced)
#             overs_bowled = convert_overs(p.overs_bowled)
#
#             nrr = 0
#             if overs_faced > 0 and overs_bowled > 0:
#                 nrr = (p.runs_scored / overs_faced) - (p.runs_conceded / overs_bowled)
#
#         else:
#             # ✅ DEFAULT VALUES (THIS WAS MISSING 🔥)
#             played = 0
#             wins = 0
#             losses = 0
#             points = 0
#             nrr = 0
#
#         result.append({
#             "team": team_name,
#             "played": played,
#             "wins": wins,
#             "losses": losses,
#             "points": points,
#             "nrr": round(nrr, 3)
#         })
#
#     # ✅ Sort
#     result.sort(
#         key=lambda x: (x["points"], x["nrr"], x["wins"]),
#         reverse=True
#     )
#
#     return result
#
#
# @router.post("/{tournament_id}/generate_knockouts")
# def generate_knockouts(tournament_id: int, db: Session = Depends(get_db)):
#     points = get_points(tournament_id, db)
#
#     top4 = points[:4]
#
#     semi1 = TournamentMatch(
#         tournament_id=tournament_id,
#         team_a=top4[0]["team"],
#         team_b=top4[3]["team"],
#         stage="semi"
#     )
#
#     semi2 = TournamentMatch(
#         tournament_id=tournament_id,
#         team_a=top4[1]["team"],
#         team_b=top4[2]["team"],
#         stage="semi"
#     )
#
#     db.add_all([semi1, semi2])
#     db.commit()
#
#     return {"message": "Semis created"}
#
#
# @router.delete("/{tournament_id}/fixtures/upcoming")
# def delete_upcoming_fixtures(tournament_id: int, db: Session = Depends(get_db)):
#     deleted = db.query(TournamentMatch).filter(
#         TournamentMatch.tournament_id == tournament_id,
#         TournamentMatch.match_id == None,
#         TournamentMatch.winner == None
#     ).delete(synchronize_session=False)
#
#     db.commit()
#
#     return {
#         "message": "Upcoming fixtures deleted",
#         "deleted": deleted
#     }
#
#
# @router.get("/{tournament_id}/teams")
# def get_teams(tournament_id: int, db: Session = Depends(get_db)):
#     teams = db.query(TournamentTeam).filter_by(
#         tournament_id=tournament_id,
#         status="approved"
#     ).all()
#
#     result = []
#
#     for t in teams:
#         team = db.query(Team).get(t.team_id)
#         team_name = team.name if team else "Unknown"
#
#         # 🔍 GROUP MAPPING
#         group_map = db.query(GroupTeam).join(
#             TournamentGroup,
#             GroupTeam.group_id == TournamentGroup.id
#         ).filter(
#             GroupTeam.team_id == t.team_id,
#             TournamentGroup.tournament_id == tournament_id
#         ).first()
#
#         group_name = None
#
#         if group_map:
#             group = db.query(TournamentGroup).get(group_map.group_id)
#             if group:
#                 group_name = group.name
#
#         # 🔥💥 ENSURE POINTS ROW EXISTS
#         existing = db.query(TournamentPoints).filter_by(
#             tournament_id=tournament_id,
#             team_name=team_name
#         ).first()
#
#         if not existing:
#             db.add(TournamentPoints(
#                 tournament_id=tournament_id,
#                 team_name=team_name,
#                 played=0,
#                 wins=0,
#                 losses=0,
#                 points=0,
#                 runs_scored=0,
#                 runs_conceded=0,
#                 overs_faced=0,
#                 overs_bowled=0
#             ))
#
#         result.append({
#             "team_id": t.team_id,
#             "team_name": team_name,
#             "group_name": group_name or "No Group"
#         })
#
#     db.commit()  # 🔥 IMPORTANT
#
#     return result
#
#
# @router.delete("/teams/{team_id}")
# def delete_team(team_id: int, db: Session = Depends(get_db)):
#     # remove mapping
#     db.query(TournamentTeam).filter(
#         TournamentTeam.team_id == team_id
#     ).delete(synchronize_session=False)
#
#     # remove fixtures
#     db.query(TournamentMatch).filter(
#         (TournamentMatch.team_a_id == team_id) |
#         (TournamentMatch.team_b_id == team_id)
#     ).delete(synchronize_session=False)
#
#     db.commit()
#
#     return {"message": "Team removed"}
#
#
# @router.post("/teams/create")
# def create_team(name: str, captain_id: int, db: Session = Depends(get_db)):
#     team = Team(name=name, captain_id=captain_id)
#
#     db.add(team)
#     db.commit()
#     db.refresh(team)
#
#     return {
#         "id": team.id,
#         "name": team.name,
#         "captain_id": team.captain_id
#     }
#
#
# @router.post("/{tournament_id}/join")
# def join_tournament(
#         tournament_id: int,
#         team_id: int,
#         db: Session = Depends(get_db),
#         user_id: int = Depends(get_current_user_id)
# ):
#     # 🔥 BLOCK ADMIN
#     admin = db.query(TournamentUser).filter_by(
#         tournament_id=tournament_id,
#         user_id=user_id,
#         role="ADMIN"
#     ).first()
#
#     if admin:
#         raise HTTPException(403, "Admin cannot join own tournament")
#
#     # 🔥 CHECK TEAM OWNERSHIP (IMPORTANT)
#     team = db.query(Team).filter_by(id=team_id).first()
#
#     if not team:
#         raise HTTPException(404, "Team not found")
#
#     if team.captain_id != user_id:
#         raise HTTPException(403, "You can only join with your team")
#
#     # ✅ TEAM FULL CHECK (ADDED)
#     # ⚠️ Replace TeamPlayer with your actual table if different
#     players_count = db.query(TeamPlayer).filter_by(team_id=team_id).count()
#
#     max_players = team.max_players if hasattr(team, "max_players") else 11
#
#     if players_count >= max_players:
#         raise HTTPException(400, "Team is already full")
#
#     # 🔥 CHECK EXISTING
#     existing = db.query(TournamentTeam).filter_by(
#         tournament_id=tournament_id,
#         team_id=team_id
#     ).first()
#
#     if existing:
#         if existing.status == "rejected":
#             raise HTTPException(400, "Request was rejected")
#         raise HTTPException(400, "Already joined")
#
#     # 🔥 CREATE ENTRY
#     entry = TournamentTeam(
#         tournament_id=tournament_id,
#         team_id=team_id,
#         status="pending"
#     )
#
#     db.add(entry)
#     db.commit()
#
#     return {
#         "success": True,
#         "message": "Request sent"
#     }
#
#
# @router.post("/{tournament_id}/approve/{team_id}")
# def approve_team(
#         tournament_id: int,
#         team_id: int,
#         db: Session = Depends(get_db),
#         user_id: int = Depends(get_current_user_id)
# ):
#     require_admin(db, user_id, tournament_id)
#
#     entry = db.query(TournamentTeam).filter_by(
#         tournament_id=tournament_id,
#         team_id=team_id
#     ).first()
#
#     if not entry:
#         raise HTTPException(404, "Not found")
#
#     if entry.status == "approved":
#         raise HTTPException(400, "Already approved")
#
#     entry.status = "approved"
#     db.commit()
#
#     return {"message": "Approved"}
#
#
# @router.get("/{tournament_id}/requests")
# def get_requests(
#         tournament_id: int,
#         db: Session = Depends(get_db),
#         user_id: int = Depends(get_current_user_id)
# ):
#     require_admin(db, user_id, tournament_id)
#
#     teams = db.query(TournamentTeam).filter_by(
#         tournament_id=tournament_id,
#         status="pending"
#     ).all()
#
#     return [
#         {
#             "team_id": t.team.id,
#             "team_name": t.team.name
#         }
#         for t in teams
#     ]
#
#
# @router.post("/{tournament_id}/reject/{team_id}")
# def reject_team(
#         tournament_id: int,
#         team_id: int,
#         db: Session = Depends(get_db),
#         user_id: int = Depends(get_current_user_id)
# ):
#     require_admin(db, user_id, tournament_id)
#
#     entry = db.query(TournamentTeam).filter_by(
#         tournament_id=tournament_id,
#         team_id=team_id
#     ).first()
#
#     if not entry:
#         raise HTTPException(404, "Not found")
#
#     if entry.status == "rejected":
#         raise HTTPException(400, "Already rejected")
#
#     entry.status = "rejected"
#     db.commit()
#
#     return {"message": "Rejected"}
#
#
# @router.post("/{tournament_id}/next_round")
# def next_round(tournament_id: int, db: Session = Depends(get_db)):
#     points = db.query(TournamentPoints).filter_by(
#         tournament_id=tournament_id
#     ).all()
#
#     sorted_teams = sorted(
#         points,
#         key=lambda x: (x.points, x.runs_scored),
#         reverse=True
#     )
#
#     top4 = sorted_teams[:4]
#
#     fixtures = generate_knockout([t.team_name for t in top4])
#
#     for a, b in fixtures:
#         db.add(TournamentMatch(
#             tournament_id=tournament_id,
#             team_a=a,
#             team_b=b,
#             match_type="knockout",
#             round=2
#         ))
#
#     db.commit()
#
#     return {"message": "Next round created"}
#
#
# @router.get("/{tournament_id}/matches")
# def get_matches(tournament_id: int, db: Session = Depends(get_db)):
#     matches = db.query(TournamentMatch).filter_by(
#         tournament_id=tournament_id
#     ).all()
#
#     result = []
#
#     for m in matches:
#         teamA = db.query(Team).get(m.team_a_id) if m.team_a_id else None
#         teamB = db.query(Team).get(m.team_b_id) if m.team_b_id else None
#
#         result.append({
#             "id": m.id,
#             "team_a_id": m.team_a_id,
#             "team_b_id": m.team_b_id,
#
#             "team_a": teamA.name if teamA else "TBD",
#             "team_b": teamB.name if teamB else "TBD",
#
#             "stage": m.match_type,
#             "winner": m.winner,
#
#             "group_id": m.group_id,
#             "match_time": m.match_time,
#
#             "is_live": False,
#         })
#
#     return result
#
#
# @router.post("/teams/{team_id}/invite")
# def create_invite(team_id: int, db: Session = Depends(get_db)):
#     code = str(uuid.uuid4())[:8]
#
#     invite = TeamInvite(
#         team_id=team_id,
#         code=code
#     )
#
#     db.add(invite)
#     db.commit()
#
#     return {
#         "code": code,
#         "link": f"https://runbhoomi.app/join-team/{code}"
#     }
#
#
# @router.post("/teams/join/{code}")
# def join_team_by_code(code: str, player_id: int, db: Session = Depends(get_db)):
#     invite = db.query(TeamInvite).filter_by(code=code).first()
#
#     if not invite:
#         raise HTTPException(404, "Invalid code")
#
#     db.add(TeamPlayer(
#         team_id=invite.team_id,
#         player_id=player_id
#     ))
#
#     db.commit()
#
#     return {"message": "Joined team"}
#
#
# @router.get("/{tournament_id}/groups")
# def get_groups(tournament_id: int, db: Session = Depends(get_db)):
#     groups = db.query(TournamentGroup).filter_by(
#         tournament_id=tournament_id
#     ).all()
#
#     return [
#         {"id": g.id, "name": g.name}
#         for g in groups
#     ]
#
#
# @router.get("/{tournament_id}/my-role")
# def get_my_role(
#         tournament_id: int,
#         db: Session = Depends(get_db),
#         user_id: int = Depends(get_current_user_id)
# ):
#     record = db.query(TournamentUser).filter_by(
#         tournament_id=tournament_id,
#         user_id=user_id
#     ).first()
#
#     if not record:
#         return {"role": "PLAYER"}
#
#     return {"role": record.role}
