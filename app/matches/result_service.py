from app.database import models


def complete_match(match, innings2):
    target = innings2.target or 0

    chasing_team_id = innings2.batting_team_id
    defending_team_id = innings2.bowling_team_id

    if innings2.runs >= target:
        wickets_left = 10 - innings2.wickets

        match.winner_team_id = chasing_team_id

        match.result = f"Won by {wickets_left} wickets"

    elif innings2.runs < target:
        margin = target - innings2.runs - 1

        match.winner_team_id = defending_team_id

        match.result = f"Won by {margin} runs"

    else:
        match.result = "Match tied"

    match.status = "completed"