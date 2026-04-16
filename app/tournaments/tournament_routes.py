from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import models
from app.database.db import get_db
from app.database.models import TournamentTeam, TournamentPoints, TournamentMatch, Team, GroupTeam, TeamInvite, \
    TeamPlayer
from app.tournaments.group_service import create_groups, round_robin, generate_knockout

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
    tournament = db.query(models.Tournament).filter_by(
        id=tournament_id
    ).first()

    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")

    # 🔥 CREATE OR GET TEAM (NEW FIX)
    team = db.query(Team).filter_by(name=team_name).first()

    if not team:
        team = Team(name=team_name)
        db.add(team)
        db.commit()
        db.refresh(team)

    # check duplicate (by team_id now)
    existing = db.query(TournamentTeam).filter_by(
        tournament_id=tournament_id,
        team_id=team.id
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Team already exists")

    # check max teams
    count = db.query(TournamentTeam).filter_by(
        tournament_id=tournament_id
    ).count()

    if count >= tournament.total_teams:
        raise HTTPException(status_code=400, detail="Max teams reached")

    entry = TournamentTeam(
        tournament_id=tournament_id,
        team_id=team.id,
        status="pending"
    )

    db.add(entry)

    # keep points same (no break)
    points = TournamentPoints(
        tournament_id=tournament_id,
        team_name=team_name
    )
    db.add(points)

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
def generate_fixtures(tournament_id: int, db: Session = Depends(get_db)):
    tournament = db.query(models.Tournament).get(tournament_id)

    if not tournament:
        raise HTTPException(404, "Tournament not found")

    teams = db.query(TournamentTeam).filter_by(
        tournament_id=tournament_id,
        status="approved"
    ).all()

    if not teams:
        raise HTTPException(400, "No approved teams")

    # ✅ IMPORTANT: prevent duplicate fixtures
    existing = db.query(TournamentMatch).filter_by(
        tournament_id=tournament_id
    ).first()

    if existing:
        raise HTTPException(400, "Fixtures already generated")

    # =========================
    # 🧠 LEAGUE / HYBRID
    # =========================
    if tournament.format in ["league", "hybrid"]:

        groups = create_groups(db, tournament_id, teams)

        # ✅ GROUP BASED
        if groups:
            for g in groups:
                group_teams = db.query(GroupTeam).filter_by(
                    group_id=g.id
                ).all()

                ids = [gt.team_id for gt in group_teams]

                fixtures = round_robin(ids)

                for a, b in fixtures:
                    db.add(TournamentMatch(
                        tournament_id=tournament_id,

                        # ✅ BOTH (IMPORTANT FOR UI + OLD CODE)
                        team_a_id=a,
                        team_b_id=b,
                        team_a=str(a),
                        team_b=str(b),

                        group_id=g.id,
                        match_type="league",
                        round=1
                    ))

        # ✅ NO GROUP
        else:
            ids = [t.team_id for t in teams]

            fixtures = round_robin(ids)

            for a, b in fixtures:
                db.add(TournamentMatch(
                    tournament_id=tournament_id,

                    # ✅ BOTH
                    team_a_id=a,
                    team_b_id=b,
                    team_a=str(a),
                    team_b=str(b),

                    match_type="league",
                    round=1
                ))

    # =========================
    # 🧠 KNOCKOUT
    # =========================
    elif tournament.format == "knockout":

        ids = [t.team_id for t in teams]

        fixtures = generate_knockout(ids)

        for a, b in fixtures:
            db.add(TournamentMatch(
                tournament_id=tournament_id,

                team_a_id=a,
                team_b_id=b,
                team_a=str(a) if a else "BYE",
                team_b=str(b) if b else "BYE",

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

    matches = db.query(models.TournamentMatch).filter(
        models.TournamentMatch.tournament_id == tournament_id,
        models.TournamentMatch.winner == None,   # not completed
        models.TournamentMatch.is_live == False  # not live
    ).all()

    if not matches:
        return {"message": "No upcoming matches to delete"}

    deleted_count = len(matches)

    for match in matches:
        db.delete(match)

    db.commit()

    return {
        "message": "Upcoming fixtures deleted",
        "deleted": deleted_count
    }


@router.get("/{tournament_id}/teams")
def get_teams(tournament_id: int, db: Session = Depends(get_db)):
    teams = db.query(TournamentTeam).filter_by(
        tournament_id=tournament_id,
        status="approved"
    ).all()

    return [
        {
            "id": t.id,  # IMPORTANT: tournament team id
            "team_id": t.team.id,
            "team_name": t.team.name
        }
        for t in teams
    ]


@router.delete("/teams/{team_id}")
def delete_team(team_id: int, db: Session = Depends(get_db)):
    entry = db.query(TournamentTeam).filter(
        TournamentTeam.id == team_id
    ).first()

    if not entry:
        raise HTTPException(status_code=404, detail="Team not found")

    db.delete(entry)
    db.commit()

    return {"message": "Team deleted"}


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


@router.get("/{tournament_id}/matches")
def get_matches(tournament_id: int, db: Session = Depends(get_db)):
    matches = db.query(TournamentMatch).filter_by(
        tournament_id=tournament_id
    ).all()

    result = []

    for m in matches:
        teamA = db.query(models.Team).get(m.team_a_id) if m.team_a_id else None
        teamB = db.query(models.Team).get(m.team_b_id) if m.team_b_id else None

        result.append({
            "id": m.id,
            "team_a": teamA.name if teamA else m.team_a,
            "team_b": teamB.name if teamB else m.team_b,
            "stage": m.match_type,
            "winner": m.winner
        })

    return result


import uuid

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