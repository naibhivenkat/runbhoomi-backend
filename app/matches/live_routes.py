# from fastapi import APIRouter, Depends
# from sqlalchemy.orm import Session
#
# from app.database import models
# from app.database.db import get_db
# from app.matches.innings_service import get_current_innings
# from app.matches.match_service import resolve_match
#
# router = APIRouter(prefix="/live")
#
#
# @router.get("/{match_id}")
# def live_score(
#         match_id: str,
#         db: Session = Depends(get_db)
# ):
#     match = resolve_match(db, match_id)
#
#     innings = get_current_innings(db, match.id)
#
#     batsmen = db.query(models.Batsman).filter(
#         models.Batsman.innings_id == innings.id,
#         models.Batsman.is_out == False
#     ).all()
#
#     return {
#         "score": f"{innings.runs}/{innings.wickets}",
#         "overs": innings.overs,
#         "target": innings.target,
#         "innings": innings.innings_no,
#         "batsmen": [
#             {
#                 "name": b.name,
#                 "runs": b.runs,
#                 "balls": b.balls
#             }
#             for b in batsmen
#         ]
#     }





from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import models
from app.database.db import get_db
from app.matches.innings_service import get_current_innings
from app.matches.match_service import resolve_match

# -------------------------------------------------------------------
# PRODUCTION-GRADE MATCH FEED API
#
# Endpoints:
#   GET /live/{match_id}
#   GET /upcoming
#   GET /completed
#
# Fixes Included:
# 1. Overs are read from database (no hardcoded values)
# 2. Score format: 7/0 (0.2/4)
# 3. Live subtitle shows toss winner + elected to bat/bowl
# 4. Completed matches include exact winning margin
# 5. Upcoming matches include proper schedule details
# 6. Robust null-safe handling
# -------------------------------------------------------------------

router = APIRouter()


# ===================================================================
# HELPERS
# ===================================================================

def _safe_team_name(team):
    """Safely extract team name."""
    if not team:
        return "TBD"

    for attr in ["short_name", "name", "team_name"]:
        if hasattr(team, attr):
            value = getattr(team, attr)
            if value:
                return value

    return "TBD"


def _safe_player_name(player):
    """Safely extract player name."""
    if not player:
        return "Unknown"

    for attr in ["full_name", "name", "player_name"]:
        if hasattr(player, attr):
            value = getattr(player, attr)
            if value:
                return value

    return "Unknown"


def _format_score(runs, wickets):
    return f"{runs}/{wickets}"


def _format_score_with_overs(runs, wickets, overs, max_overs):
    """
    Example:
        7/0 (0.2/4)
        156/7 (20.0/20)
    """
    if max_overs:
        return f"{runs}/{wickets} ({overs}/{max_overs})"
    return f"{runs}/{wickets} ({overs})"


def _get_max_overs(match):
    """
    Detect maximum overs from match object.
    Supports different field names.
    """
    for attr in [
        "overs_per_innings",
        "max_overs",
        "total_overs",
        "overs",
        "match_overs",
    ]:
        if hasattr(match, attr):
            value = getattr(match, attr)
            if value:
                return value
    return None


def _get_toss_info(match):
    """
    Returns:
        'SRH won the toss and elected to bat'
    """
    toss_winner = None
    decision = None

    # Toss winner
    if hasattr(match, "toss_winner_team") and match.toss_winner_team:
        toss_winner = match.toss_winner_team
    elif hasattr(match, "toss_winner") and match.toss_winner:
        toss_winner = match.toss_winner

    # Decision
    for attr in ["toss_decision", "elected_to", "decision"]:
        if hasattr(match, attr):
            decision = getattr(match, attr)
            if decision:
                break

    if toss_winner and decision:
        return f"{_safe_team_name(toss_winner)} won the toss and elected to {decision}"

    if toss_winner:
        return f"{_safe_team_name(toss_winner)} won the toss"

    return "Match starting soon"


def _get_match_status_text(match, innings):
    """
    Live status text:
    - Before start: toss info
    - 1st innings: toss info
    - 2nd innings: target information
    """
    if innings and getattr(innings, "innings_no", 1) == 1:
        return _get_toss_info(match)

    if innings and getattr(innings, "innings_no", 1) == 2:
        target = getattr(innings, "target", None)
        if target:
            return f"Target: {target} runs"
        return "2nd innings in progress"

    return _get_toss_info(match)


def _calculate_result_text(db: Session, match):
    """
    Returns:
      - 'RCB won by 23 runs'
      - 'SRH won by 5 wickets'
      - 'Match tied'
      - 'No result'
    """

    # If explicit result text exists in DB, use it
    for attr in ["result_text", "result", "match_result"]:
        if hasattr(match, attr):
            value = getattr(match, attr)
            if isinstance(value, str) and value.strip():
                return value.strip()

    innings_list = (
        db.query(models.Innings)
        .filter(models.Innings.match_id == match.id)
        .order_by(models.Innings.innings_no.asc())
        .all()
    )

    if len(innings_list) < 2:
        return "Match completed"

    first = innings_list[0]
    second = innings_list[1]

    team1 = getattr(first, "batting_team", None)
    team2 = getattr(second, "batting_team", None)

    first_runs = getattr(first, "runs", 0)
    second_runs = getattr(second, "runs", 0)
    second_wickets = getattr(second, "wickets", 0)

    # Second team chased successfully
    if second_runs >= getattr(second, "target", first_runs + 1):
        wickets_remaining = 10 - second_wickets
        return f"{_safe_team_name(team2)} won by {wickets_remaining} wickets"

    # First team defended
    if first_runs > second_runs:
        margin = first_runs - second_runs
        return f"{_safe_team_name(team1)} won by {margin} runs"

    # Tie
    if first_runs == second_runs:
        return "Match tied"

    return "No result"


def _serialize_batsmen(db: Session, innings):
    if not innings:
        return []

    batsmen = (
        db.query(models.Batsman)
        .filter(
            models.Batsman.innings_id == innings.id,
            models.Batsman.is_out == False
        )
        .all()
    )

    return [
        {
            "name": _safe_player_name(b),
            "runs": getattr(b, "runs", 0),
            "balls": getattr(b, "balls", 0),
        }
        for b in batsmen
    ]


# ===================================================================
# LIVE SCORE
# ===================================================================

@router.get("/live/{match_id}")
def live_score(
    match_id: str,
    db: Session = Depends(get_db),
):
    """
    Live match feed for home screen.
    """

    match = resolve_match(db, match_id)
    innings = get_current_innings(db, match.id)

    if not innings:
        return {
            "match_id": str(match.id),
            "status": "upcoming",
            "subtitle": _get_toss_info(match),
            "team1": _safe_team_name(getattr(match, "team1", None)),
            "team2": _safe_team_name(getattr(match, "team2", None)),
            "score": None,
            "overs": None,
            "display_score": None,
            "target": None,
            "innings": None,
            "batsmen": [],
        }

    max_overs = _get_max_overs(match)

    return {
        "match_id": str(match.id),
        "status": "live",

        # Teams
        "team1": _safe_team_name(getattr(match, "team1", None)),
        "team2": _safe_team_name(getattr(match, "team2", None)),

        # Core score fields
        "score": _format_score(
            getattr(innings, "runs", 0),
            getattr(innings, "wickets", 0),
        ),
        "overs": getattr(innings, "overs", "0.0"),
        "max_overs": max_overs,

        # UI ready display: 7/0 (0.2/4)
        "display_score": _format_score_with_overs(
            getattr(innings, "runs", 0),
            getattr(innings, "wickets", 0),
            getattr(innings, "overs", "0.0"),
            max_overs,
        ),

        # Additional info
        "target": getattr(innings, "target", None),
        "innings": getattr(innings, "innings_no", 1),

        # Proper subtitle
        "subtitle": _get_match_status_text(match, innings),

        # Live batsmen
        "batsmen": _serialize_batsmen(db, innings),
    }


# ===================================================================
# UPCOMING MATCHES
# ===================================================================

@router.get("/upcoming")
def upcoming_matches(db: Session = Depends(get_db)):
    """
    Matches that are not started yet.
    """

    matches = (
        db.query(models.Match)
        .filter(
            func.lower(getattr(models.Match, "status")).
            in_(["scheduled", "upcoming", "not_started"])
        )
        .order_by(getattr(models.Match, "scheduled_at", models.Match.created_at))
        .all()
    )

    result = []

    for match in matches:
        result.append({
            "match_id": str(match.id),
            "team1": _safe_team_name(getattr(match, "team1", None)),
            "team2": _safe_team_name(getattr(match, "team2", None)),
            "overs": _get_max_overs(match),
            "subtitle": "Match starts soon",
            "scheduled_at": (
                getattr(match, "scheduled_at", None).isoformat()
                if getattr(match, "scheduled_at", None)
                else None
            ),
            "venue": getattr(match, "venue", None),
            "status": "upcoming",
        })

    return result


# ===================================================================
# COMPLETED MATCHES
# ===================================================================

@router.get("/completed")
def completed_matches(db: Session = Depends(get_db)):
    """
    Completed match history with exact result and scores.
    """

    matches = (
        db.query(models.Match)
        .filter(
            func.lower(getattr(models.Match, "status")).
            in_(["completed", "finished", "ended"])
        )
        .order_by(getattr(models.Match, "updated_at", models.Match.created_at).desc())
        .all()
    )

    result = []

    for match in matches:
        innings_list = (
            db.query(models.Innings)
            .filter(models.Innings.match_id == match.id)
            .order_by(models.Innings.innings_no.asc())
            .all()
        )

        team1_score = None
        team2_score = None

        if len(innings_list) >= 1:
            i1 = innings_list[0]
            team1_score = _format_score(
                getattr(i1, "runs", 0),
                getattr(i1, "wickets", 0),
            )

        if len(innings_list) >= 2:
            i2 = innings_list[1]
            team2_score = _format_score(
                getattr(i2, "runs", 0),
                getattr(i2, "wickets", 0),
            )

        result.append({
            "match_id": str(match.id),
            "team1": _safe_team_name(getattr(match, "team1", None)),
            "team2": _safe_team_name(getattr(match, "team2", None)),
            "team1_score": team1_score,
            "team2_score": team2_score,
            "overs": _get_max_overs(match),
            "result": _calculate_result_text(db, match),
            "status": "completed",
            "completed_at": (
                getattr(match, "updated_at", None).isoformat()
                if getattr(match, "updated_at", None)
                else None
            ),
        })

    return result