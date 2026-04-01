from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import models
from app.database.db import get_db
from app.database.models import TournamentTeam, TournamentPoints, TournamentMatch, Team

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
    logo_url: str | None = None
    banner_url: str | None = None


@router.post("/create")
def create_tournament(data: TournamentCreate, db: Session = Depends(get_db)):
    t = models.Tournament(**data.dict())

    db.add(t)
    db.commit()
    db.refresh(t)

    return {"id": t.id, "message": "Tournament created"}


# @router.post("/{tournament_id}/add_team")
# def add_team(tournament_id: int, team_name: str, db: Session = Depends(get_db)):
#
#     # ✅ check tournament exists (FIX ADDED)
#     tournament = db.query(models.Tournament).filter_by(
#         id=tournament_id
#     ).first()
#
#     if not tournament:
#         raise HTTPException(status_code=404, detail="Tournament not found")
#
#     # check duplicate
#     existing = db.query(TournamentTeam).filter_by(
#         tournament_id=tournament_id,
#         team_name=team_name
#     ).first()
#
#     if existing:
#         raise HTTPException(status_code=400, detail="Team already exists")
#
#     # check max teams
#     count = db.query(TournamentTeam).filter_by(
#         tournament_id=tournament_id
#     ).count()
#
#     if count >= tournament.total_teams:
#         raise HTTPException(status_code=400, detail="Max teams reached")
#
#     team = TournamentTeam(
#         tournament_id=tournament_id,
#         team_name=team_name
#     )
#
#     db.add(team)  # ✅ FIX: removed duplicate db.add()
#
#     # create points row
#     points = TournamentPoints(
#         tournament_id=tournament_id,
#         team_name=team_name
#     )
#     db.add(points)
#
#     db.commit()
#
#     return {"message": "Team added"}


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
        status="approved"  # keep workflow same
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
    teams = db.query(TournamentTeam).filter_by(
        tournament_id=tournament_id
    ).all()

    team_names = [t.team_name for t in teams]

    matches = []

    for i in range(len(team_names)):
        for j in range(i + 1, len(team_names)):
            match = TournamentMatch(
                tournament_id=tournament_id,
                team_a=team_names[i],
                team_b=team_names[j],
                stage="league"
            )
            db.add(match)
            matches.append(match)

    db.commit()

    return {"matches_created": len(matches)}


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


@router.get("/{tournament_id}/matches")
def get_matches(tournament_id: int, db: Session = Depends(get_db)):
    matches = db.query(TournamentMatch).filter_by(
        tournament_id=tournament_id
    ).all()

    return [
        {
            "id": m.id,
            "team_a": m.team_a,
            "team_b": m.team_b,
            "stage": m.stage,
            "winner": m.winner
        }
        for m in matches
    ]


# @router.get("/{tournament_id}/teams")
# def get_teams(tournament_id: int, db: Session = Depends(get_db)):
#
#     teams = db.query(TournamentTeam).filter_by(
#         tournament_id=tournament_id,
#         status="approved"
#     ).all()
#
#     return [
#         {
#             "id": t.team.id,
#             "team_name": t.team.name,
#             "captain_id": t.team.captain_id
#         }
#         for t in teams
#     ]

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


# @router.delete("/teams/{team_id}")
# def delete_team(team_id: int, db: Session = Depends(get_db)):
#     team = db.query(TournamentTeam).filter(
#         TournamentTeam.id == team_id
#     ).first()
#
#     if not team:
#         raise HTTPException(status_code=404, detail="Team not found")
#
#     db.delete(team)
#     db.commit()
#
#     return {"message": "Team deleted"}

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

    return team


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
