from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
import uuid

from app.database import models
from app.database.db import get_db
from app.database.models import TournamentTeam, TournamentPoints, TournamentMatch, Team, GroupTeam, TeamInvite, \
    TeamPlayer, TournamentGroup
from app.tournaments.group_service import create_groups, round_robin, generate_knockout, paired_rounds

router = APIRouter(prefix="/tournaments")


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
def create_tournament(data: TournamentCreate, db: Session = Depends(get_db)):
    t = models.Tournament(**data.dict())

    db.add(t)
    db.commit()
    db.refresh(t)

    return {"id": t.id, "message": "Tournament created"}


@router.post("/matches/{tm_id}/init")
def init_match_from_fixture(tm_id: int, db: Session = Depends(get_db)):
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
def add_team(tournament_id: int, team_name: str, db: Session = Depends(get_db)):
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


# @router.post("/{tournament_id}/generate_fixtures")
# def generate_fixtures(tournament_id: int, db: Session = Depends(get_db)):
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
#     # =========================
#     # 🔥 DELETE OLD FIXTURES
#     # =========================
#     db.query(TournamentMatch).filter(
#         TournamentMatch.tournament_id == tournament_id
#     ).delete(synchronize_session=False)
#
#     # =========================
#     # 🔥 DELETE ONLY THIS TOURNAMENT GROUP DATA
#     # =========================
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
#     # =========================
#     # 🟢 LEAGUE / HYBRID
#     # =========================
#     if tournament.format in ["league", "hybrid"]:
#
#         # ✅ CREATE GROUPS
#         groups = create_groups(db, tournament_id, teams)
#
#         print("GROUPS CREATED:", groups)  # DEBUG
#
#         # ❌ SMALL → NO GROUPS
#         if not groups:
#             fixtures = paired_rounds(ids)
#
#             for a, b in fixtures:
#                 teamA = db.query(Team).get(a)
#                 teamB = db.query(Team).get(b)
#
#                 db.add(TournamentMatch(
#                     tournament_id=tournament_id,
#                     team_a_id=a,
#                     team_b_id=b,
#                     team_a=teamA.name if teamA else "TBD",
#                     team_b=teamB.name if teamB else "TBD",
#                     match_type="league",
#                     round=1
#                 ))
#
#         # ✅ GROUP BASED
#         else:
#             for g in groups:
#
#                 group_teams = db.query(GroupTeam).filter_by(
#                     group_id=g.id
#                 ).all()
#
#                 team_ids = [gt.team_id for gt in group_teams]
#
#                 print(f"Group {g.name} teams:", team_ids)  # DEBUG
#
#                 fixtures = paired_rounds(team_ids)
#
#                 for a, b in fixtures:
#                     teamA = db.query(Team).get(a)
#                     teamB = db.query(Team).get(b)
#
#                     db.add(TournamentMatch(
#                         tournament_id=tournament_id,
#                         team_a_id=a,
#                         team_b_id=b,
#                         team_a=teamA.name if teamA else "TBD",
#                         team_b=teamB.name if teamB else "TBD",
#                         match_type="league",
#                         group_id=g.id,
#                         round=1
#                     ))
#
#     # =========================
#     # 🔴 KNOCKOUT
#     # =========================
#     elif tournament.format == "knockout":
#
#         fixtures = generate_knockout(ids)
#
#         for a, b in fixtures:
#             teamA = db.query(Team).get(a) if a else None
#             teamB = db.query(Team).get(b) if b else None
#
#             db.add(TournamentMatch(
#                 tournament_id=tournament_id,
#                 team_a_id=a,
#                 team_b_id=b,
#                 team_a=teamA.name if teamA else "BYE",
#                 team_b=teamB.name if teamB else "BYE",
#                 match_type="knockout",
#                 round=1
#             ))
#
#     db.commit()
#
#     return {"message": "Fixtures created successfully"}


from fastapi import Query

@router.post("/{tournament_id}/generate_fixtures")
def generate_fixtures(
    tournament_id: int,
    group_count: int = Query(2),   
    db: Session = Depends(get_db)
):
    tournament = db.query(models.Tournament).get(tournament_id)

    if not tournament:
        raise HTTPException(404, "Tournament not found")

    teams = db.query(TournamentTeam).filter_by(
        tournament_id=tournament_id,
        status="approved"
    ).all()

    if len(teams) < 2:
        raise HTTPException(400, "Not enough teams")

    # =========================
    # 🔥 DELETE OLD FIXTURES
    # =========================
    db.query(TournamentMatch).filter(
        TournamentMatch.tournament_id == tournament_id
    ).delete(synchronize_session=False)

    # =========================
    # 🔥 DELETE ONLY THIS TOURNAMENT GROUP DATA
    # =========================
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

    # =========================
    # 🟢 LEAGUE / HYBRID
    # =========================
    if tournament.format in ["league", "hybrid"]:

        # ✅ CREATE GROUPS WITH USER INPUT
        groups = create_groups(db, tournament_id, teams, group_count)

        print("GROUPS CREATED:", groups)

        # ❌ fallback (rare case)
        if not groups:
            fixtures = paired_rounds(ids)

            for a, b in fixtures:
                teamA = db.query(Team).get(a)
                teamB = db.query(Team).get(b)

                db.add(TournamentMatch(
                    tournament_id=tournament_id,
                    team_a_id=a,
                    team_b_id=b,
                    team_a=teamA.name if teamA else "TBD",
                    team_b=teamB.name if teamB else "TBD",
                    match_type="league",
                    round=1
                ))

        # ✅ GROUP BASED
        else:
            for g in groups:

                group_teams = db.query(GroupTeam).filter_by(
                    group_id=g.id
                ).all()

                team_ids = [gt.team_id for gt in group_teams]

                print(f"{g.name} teams:", team_ids)

                fixtures = paired_rounds(team_ids)

                for a, b in fixtures:
                    teamA = db.query(Team).get(a)
                    teamB = db.query(Team).get(b)

                    db.add(TournamentMatch(
                        tournament_id=tournament_id,
                        team_a_id=a,
                        team_b_id=b,
                        team_a=teamA.name if teamA else "TBD",
                        team_b=teamB.name if teamB else "TBD",
                        match_type="league",
                        group_id=g.id,   # 🔥 important
                        round=1
                    ))

    # =========================
    # 🔴 KNOCKOUT
    # =========================
    elif tournament.format == "knockout":

        fixtures = generate_knockout(ids)

        for a, b in fixtures:
            teamA = db.query(Team).get(a) if a else None
            teamB = db.query(Team).get(b) if b else None

            db.add(TournamentMatch(
                tournament_id=tournament_id,
                team_a_id=a,
                team_b_id=b,
                team_a=teamA.name if teamA else "BYE",
                team_b=teamB.name if teamB else "BYE",
                match_type="knockout",
                round=1
            ))

    db.commit()

    return {"message": "Fixtures created successfully"}

@router.get("/{tournament_id}/points")
def get_points(tournament_id: int, db: Session = Depends(get_db)):
    points = db.query(TournamentPoints).filter_by(
        tournament_id=tournament_id
    ).all()

    result = []

    for p in points:
        nrr = 0
        if p.overs_faced > 0 and p.overs_bowled > 0:
            nrr = (p.runs_scored / p.overs_faced) - (p.runs_conceded / p.overs_bowled)

        result.append({
            "team": p.team_name,
            "points": p.points,
            "played": p.played,
            "wins": p.wins,
            "nrr": round(nrr, 2)
        })

    result.sort(key=lambda x: (x["points"], x["nrr"]), reverse=True)

    return result


@router.post("/{tournament_id}/generate_knockouts")
def generate_knockouts(tournament_id: int, db: Session = Depends(get_db)):
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
def delete_upcoming_fixtures(tournament_id: int, db: Session = Depends(get_db)):
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

#
# @router.get("/{tournament_id}/teams")
# def get_teams(tournament_id: int, db: Session = Depends(get_db)):
#     teams = db.query(models.TournamentTeam).filter(
#         models.TournamentTeam.tournament_id == tournament_id,
#         models.TournamentTeam.status == "approved"
#     ).all()
#
#     result = []
#
#     for t in teams:
#         team = t.team
#
#         # ✅ COUNT PLAYERS FROM TEAMPLAYER
#         count = db.query(models.TeamPlayer).filter(
#             models.TeamPlayer.team_id == team.id
#         ).count()
#
#         result.append({
#             "team_id": team.id,
#             "team_name": team.name,
#             "player_count": count
#         })
#
#     return result


@router.get("/{tournament_id}/teams")
def get_teams(tournament_id: int, db: Session = Depends(get_db)):

    teams = db.query(TournamentTeam).filter_by(
        tournament_id=tournament_id,
        status="approved"
    ).all()

    result = []

    for t in teams:
        team = db.query(Team).get(t.team_id)

        # 🔥 find group mapping for THIS tournament only
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

        result.append({
            "team_id": t.team_id,
            "team_name": team.name if team else "Unknown",
            "group_name": group_name or "No Group"
        })

    return result


@router.delete("/teams/{team_id}")
def delete_team(team_id: int, db: Session = Depends(get_db)):
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
def create_team(name: str, captain_id: int, db: Session = Depends(get_db)):
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
def join_tournament(tournament_id: int, team_id: int, db: Session = Depends(get_db)):
    existing = db.query(TournamentTeam).filter_by(
        tournament_id=tournament_id,
        team_id=team_id
    ).first()

    if existing:
        raise HTTPException(400, "Already joined")

    entry = TournamentTeam(
        tournament_id=tournament_id,
        team_id=team_id,
        status="pending"
    )

    db.add(entry)
    db.commit()

    return {"message": "Request sent"}


@router.post("/{tournament_id}/approve/{team_id}")
def approve_team(tournament_id: int, team_id: int, db: Session = Depends(get_db)):
    entry = db.query(TournamentTeam).filter_by(
        tournament_id=tournament_id,
        team_id=team_id
    ).first()

    if not entry:
        raise HTTPException(404, "Not found")

    entry.status = "approved"

    db.commit()

    return {"message": "Approved"}


@router.get("/{tournament_id}/requests")
def get_requests(tournament_id: int, db: Session = Depends(get_db)):
    teams = db.query(TournamentTeam).filter_by(
        tournament_id=tournament_id,
        status="pending"
    ).all()

    return [
        {
            "team_id": t.team.id,
            "team_name": t.team.name
        }
        for t in teams
    ]


@router.post("/{tournament_id}/reject/{team_id}")
def reject_team(
        tournament_id: int,
        team_id: int,
        db: Session = Depends(get_db)):
    entry = db.query(TournamentTeam).filter_by(
        tournament_id=tournament_id,
        team_id=team_id
    ).first()

    if not entry:
        raise HTTPException(404, "Not found")

    entry.status = "rejected"
    db.commit()

    return {"message": "Rejected"}


@router.post("/{tournament_id}/next_round")
def next_round(tournament_id: int, db: Session = Depends(get_db)):
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
#             # ✅ ALWAYS SEND NAMES FROM TEAM TABLE
#             "team_a": teamA.name if teamA else "TBD",
#             "team_b": teamB.name if teamB else "TBD",
#
#             "stage": m.match_type,
#             "winner": m.winner,
#
#             # optional but useful
#             "is_live": getattr(m, "is_live", False),
#             "match_time": getattr(m, "match_time", None),
#         })
#
#     return result

@router.get("/{tournament_id}/matches")
def get_matches(tournament_id: int, db: Session = Depends(get_db)):
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

            # ✅ ALWAYS FETCH FROM TEAM TABLE
            "team_a": teamA.name if teamA else "TBD",
            "team_b": teamB.name if teamB else "TBD",

            "stage": m.match_type,
            "winner": m.winner,

            # 🔥 IMPORTANT (THIS WAS MISSING / WRONG)
            "group_id": m.group_id,

            "is_live": False,
            "match_time": None,
        })

    return result


@router.post("/teams/{team_id}/invite")
def create_invite(team_id: int, db: Session = Depends(get_db)):
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
def join_team_by_code(code: str, player_id: int, db: Session = Depends(get_db)):
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
def get_groups(tournament_id: int, db: Session = Depends(get_db)):
    groups = db.query(TournamentGroup).filter_by(
        tournament_id=tournament_id
    ).all()

    return [
        {"id": g.id, "name": g.name}
        for g in groups
    ]
