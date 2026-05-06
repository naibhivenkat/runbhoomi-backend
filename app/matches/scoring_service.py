from sqlalchemy.orm import Session

from app.database import models


def recalculate_innings(db: Session, innings):
    balls = db.query(models.Ball).filter(
        models.Ball.innings_id == innings.id
    ).all()

    runs = sum((b.runs or 0) + (b.extra_runs or 0) for b in balls)

    wickets = sum(1 for b in balls if b.is_wicket)

    legal_balls = sum(1 for b in balls if b.is_legal_ball)

    overs = f"{legal_balls // 6}.{legal_balls % 6}"

    innings.runs = runs
    innings.wickets = wickets
    innings.overs = overs

    update_bowler_stats(db, innings)


def update_bowler_stats(db: Session, innings):
    bowlers = db.query(models.Bowler).filter(
        models.Bowler.innings_id == innings.id
    ).all()

    for bowler in bowlers:
        balls = db.query(models.Ball).filter(
            models.Ball.innings_id == innings.id,
            models.Ball.bowler_id == bowler.player_id
        ).all()

        legal_balls = sum(1 for b in balls if b.is_legal_ball)

        overs = f"{legal_balls // 6}.{legal_balls % 6}"

        runs = sum((b.runs or 0) + (b.extra_runs or 0) for b in balls)

        wickets = sum(1 for b in balls if b.is_wicket)

        economy = 0

        if legal_balls > 0:
            economy = round(runs / (legal_balls / 6), 2)

        bowler.overs = overs
        bowler.runs = runs
        bowler.wickets = wickets
        bowler.economy = economy