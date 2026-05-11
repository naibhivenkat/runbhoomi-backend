#
#
# from datetime import datetime
# from fastapi import APIRouter, Depends
# from sqlalchemy.orm import Session
# from sqlalchemy import func
#
# from app.database import models
# from app.database.db import get_db
# from app.matches.innings_service import get_current_innings
# from app.matches.match_service import resolve_match
#
#
# router = APIRouter()
#
#
# # ===================================================================
# # HELPERS
# # ===================================================================
#
# def _safe_team_name(team):
#     """Safely extract team name."""
#     if not team:
#         return "TBD"
#
#     for attr in ["short_name", "name", "team_name"]:
#         if hasattr(team, attr):
#             value = getattr(team, attr)
#             if value:
#                 return value
#
#     return "TBD"
#
#
# def _safe_player_name(player):
#     """Safely extract player name."""
#     if not player:
#         return "Unknown"
#
#     for attr in ["full_name", "name", "player_name"]:
#         if hasattr(player, attr):
#             value = getattr(player, attr)
#             if value:
#                 return value
#
#     return "Unknown"
#
#
# def _format_score(runs, wickets):
#     return f"{runs}/{wickets}"
#
#
# def _format_score_with_overs(runs, wickets, overs, max_overs):
#     """
#     Example:
#         7/0 (0.2/4)
#         156/7 (20.0/20)
#     """
#     if max_overs:
#         return f"{runs}/{wickets} ({overs}/{max_overs})"
#     return f"{runs}/{wickets} ({overs})"
#
#
# def _get_max_overs(match):
#     """
#     Detect maximum overs from match object.
#     Supports different field names.
#     """
#     for attr in [
#         "overs_per_innings",
#         "max_overs",
#         "total_overs",
#         "overs",
#         "match_overs",
#     ]:
#         if hasattr(match, attr):
#             value = getattr(match, attr)
#             if value:
#                 return value
#     return None
#
#
# def _get_toss_info(match):
#     """
#     Returns:
#         'SRH won the toss and elected to bat'
#     """
#     toss_winner = None
#     decision = None
#
#     # Toss winner
#     if hasattr(match, "toss_winner_team") and match.toss_winner_team:
#         toss_winner = match.toss_winner_team
#     elif hasattr(match, "toss_winner") and match.toss_winner:
#         toss_winner = match.toss_winner
#
#     # Decision
#     for attr in ["toss_decision", "elected_to", "decision"]:
#         if hasattr(match, attr):
#             decision = getattr(match, attr)
#             if decision:
#                 break
#
#     if toss_winner and decision:
#         return f"{_safe_team_name(toss_winner)} won the toss and elected to {decision}"
#
#     if toss_winner:
#         return f"{_safe_team_name(toss_winner)} won the toss"
#
#     return "Match starting soon"
#
#
# def _get_match_status_text(match, innings):
#     """
#     Live status text:
#     - Before start: toss info
#     - 1st innings: toss info
#     - 2nd innings: target information
#     """
#     if innings and getattr(innings, "innings_no", 1) == 1:
#         return _get_toss_info(match)
#
#     if innings and getattr(innings, "innings_no", 1) == 2:
#         target = getattr(innings, "target", None)
#         if target:
#             return f"Target: {target} runs"
#         return "2nd innings in progress"
#
#     return _get_toss_info(match)
#
#
# def _calculate_result_text(db: Session, match):
#     """
#     Returns:
#       - 'RCB won by 23 runs'
#       - 'SRH won by 5 wickets'
#       - 'Match tied'
#       - 'No result'
#     """
#
#     # If explicit result text exists in DB, use it
#     for attr in ["result_text", "result", "match_result"]:
#         if hasattr(match, attr):
#             value = getattr(match, attr)
#             if isinstance(value, str) and value.strip():
#                 return value.strip()
#
#     innings_list = (
#         db.query(models.MatchInnings)
#         .filter(models.MatchInnings.match_id == match.id)
#         .order_by(models.MatchInnings.innings_no.asc())
#         .all()
#     )
#
#     if len(innings_list) < 2:
#         return "Match completed"
#
#     first = innings_list[0]
#     second = innings_list[1]
#
#     team1 = getattr(first, "batting_team", None)
#     team2 = getattr(second, "batting_team", None)
#
#     first_runs = getattr(first, "runs", 0)
#     second_runs = getattr(second, "runs", 0)
#     second_wickets = getattr(second, "wickets", 0)
#
#     # Second team chased successfully
#     if second_runs >= getattr(second, "target", first_runs + 1):
#         wickets_remaining = 10 - second_wickets
#         return f"{_safe_team_name(team2)} won by {wickets_remaining} wickets"
#
#     # First team defended
#     if first_runs > second_runs:
#         margin = first_runs - second_runs
#         return f"{_safe_team_name(team1)} won by {margin} runs"
#
#     # Tie
#     if first_runs == second_runs:
#         return "Match tied"
#
#     return "No result"
#
#
# def _serialize_batsmen(db: Session, innings):
#     if not innings:
#         return []
#
#     batsmen = (
#         db.query(models.Batsman)
#         .filter(
#             models.Batsman.innings_id == innings.id,
#             models.Batsman.is_out == False
#         )
#         .all()
#     )
#
#     return [
#         {
#             "name": _safe_player_name(b),
#             "runs": getattr(b, "runs", 0),
#             "balls": getattr(b, "balls", 0),
#         }
#         for b in batsmen
#     ]
#
#
# # ===================================================================
# # LIVE SCORE
# # ===================================================================
#
# @router.get("/live/{match_id}")
# def live_score(
#     match_id: str,
#     db: Session = Depends(get_db),
# ):
#     """
#     Live match feed for home screen.
#     """
#
#     match = resolve_match(db, match_id)
#     innings = get_current_innings(db, match.id)
#
#     if not innings:
#         return {
#             "match_id": str(match.id),
#             "status": "upcoming",
#             "subtitle": _get_toss_info(match),
#             "team1": _safe_team_name(getattr(match, "team1", None)),
#             "team2": _safe_team_name(getattr(match, "team2", None)),
#             "score": None,
#             "overs": None,
#             "display_score": None,
#             "target": None,
#             "innings": None,
#             "batsmen": [],
#         }
#
#     max_overs = _get_max_overs(match)
#
#     return {
#         "match_id": str(match.id),
#         "status": "live",
#
#         # Teams
#         "team1": _safe_team_name(getattr(match, "team1", None)),
#         "team2": _safe_team_name(getattr(match, "team2", None)),
#
#         # Core score fields
#         "score": _format_score(
#             getattr(innings, "runs", 0),
#             getattr(innings, "wickets", 0),
#         ),
#         "overs": getattr(innings, "overs", "0.0"),
#         "max_overs": max_overs,
#
#         # UI ready display: 7/0 (0.2/4)
#         "display_score": _format_score_with_overs(
#             getattr(innings, "runs", 0),
#             getattr(innings, "wickets", 0),
#             getattr(innings, "overs", "0.0"),
#             max_overs,
#         ),
#
#         # Additional info
#         "target": getattr(innings, "target", None),
#         "innings": getattr(innings, "innings_no", 1),
#
#         # Proper subtitle
#         "subtitle": _get_match_status_text(match, innings),
#
#         # Live batsmen
#         "batsmen": _serialize_batsmen(db, innings),
#     }
#
#
# # ===================================================================
# # UPCOMING MATCHES
# # ===================================================================
#
# @router.get("/upcoming")
# def upcoming_matches(db: Session = Depends(get_db)):
#     """
#     Matches that are not started yet.
#     """
#
#     matches = (
#         db.query(models.Match)
#         .filter(
#             func.lower(getattr(models.Match, "status")).
#             in_(["scheduled", "upcoming", "not_started"])
#         )
#         .order_by(getattr(models.Match, "scheduled_at", models.Match.created_at))
#         .all()
#     )
#
#     result = []
#
#     for match in matches:
#         result.append({
#             "match_id": str(match.id),
#             "team1": _safe_team_name(getattr(match, "team1", None)),
#             "team2": _safe_team_name(getattr(match, "team2", None)),
#             "overs": _get_max_overs(match),
#             "subtitle": "Match starts soon",
#             "scheduled_at": (
#                 getattr(match, "scheduled_at", None).isoformat()
#                 if getattr(match, "scheduled_at", None)
#                 else None
#             ),
#             "venue": getattr(match, "venue", None),
#             "status": "upcoming",
#         })
#
#     return result
#
#
# # ===================================================================
# # COMPLETED MATCHES
# # ===================================================================
#
# @router.get("/completed")
# def completed_matches(db: Session = Depends(get_db)):
#     """
#     Completed match history with exact result and scores.
#     """
#
#     matches = (
#         db.query(models.Match)
#         .filter(
#             func.lower(getattr(models.Match, "status")).
#             in_(["completed", "finished", "ended"])
#         )
#         .order_by(getattr(models.Match, "updated_at", models.Match.created_at).desc())
#         .all()
#     )
#
#     result = []
#
#     for match in matches:
#         innings_list = (
#             db.query(models.MatchInnings)
#             .filter(models.MatchInnings.match_id == match.id)
#             .order_by(models.MatchInnings.innings_no.asc())
#             .all()
#         )
#
#         team1_score = None
#         team2_score = None
#
#         if len(innings_list) >= 1:
#             i1 = innings_list[0]
#             team1_score = _format_score(
#                 getattr(i1, "runs", 0),
#                 getattr(i1, "wickets", 0),
#             )
#
#         if len(innings_list) >= 2:
#             i2 = innings_list[1]
#             team2_score = _format_score(
#                 getattr(i2, "runs", 0),
#                 getattr(i2, "wickets", 0),
#             )
#
#         result.append({
#             "match_id": str(match.id),
#             "team1": _safe_team_name(getattr(match, "team1", None)),
#             "team2": _safe_team_name(getattr(match, "team2", None)),
#             "team1_score": team1_score,
#             "team2_score": team2_score,
#             "overs": _get_max_overs(match),
#             "result": _calculate_result_text(db, match),
#             "status": "completed",
#             "completed_at": (
#                 getattr(match, "updated_at", None).isoformat()
#                 if getattr(match, "updated_at", None)
#                 else None
#             ),
#         })
#
#     return result



from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import models
from app.database.db import get_db
from app.matches.innings_service import get_current_innings
from app.matches.match_service import resolve_match


router = APIRouter()


# ===================================================================
# HELPERS
# ===================================================================

def _safe_team_name(team):
    """Safely extract a team name."""
    if not team:
        return "TBD"

    for attr in ["short_name", "name", "team_name"]:
        if hasattr(team, attr):
            value = getattr(team, attr)
            if value:
                return value

    return "TBD"


def _safe_player_name(player):
    """Safely extract a player name."""
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
        7/0 (0.2/1)
        156/7 (20.0/20)
    """
    if max_overs:
        return f"{runs}/{wickets} ({overs}/{max_overs})"
    return f"{runs}/{wickets} ({overs})"


def _get_max_overs(match):
    """
    Detect maximum overs from the Match object.

    Priority:
    1. total_overs (actual column in models.py)
    2. legacy aliases for compatibility
    """
    for attr in [
        "total_overs",         # <-- actual Match model column
        "overs_per_innings",
        "max_overs",
        "overs",
        "match_overs",
    ]:
        if hasattr(match, attr):
            value = getattr(match, attr)
            if value is not None and value != 0:
                return int(value)

    return None


def _normalize_toss_decision(decision):
    """
    Converts:
      BATTING -> Bat
      BAT     -> Bat
      bat     -> Bat
      BOWLING -> Bowl
      BOWL    -> Bowl
      bowl    -> Bowl
    """
    if not decision:
        return None

    value = str(decision).strip().upper()

    if value in ["BAT", "BATTING"]:
        return "Bat"

    if value in ["BOWL", "BOWLING"]:
        return "Bowl"

    return str(decision).title()


def _get_toss_info(match):
    """
    Returns:
        'RCB elected to Bat'
        'SRH elected to Bowl'
        'RCB won the toss'
        'Match starting soon'
    """

    toss_team = None

    # Preferred relationship added in models.py
    if hasattr(match, "toss_winner_team") and match.toss_winner_team:
        toss_team = match.toss_winner_team

    # Fallbacks
    elif hasattr(match, "toss_winner") and match.toss_winner:
        toss_team = match.toss_winner

    decision = None
    for attr in ["toss_decision", "elected_to", "decision"]:
        if hasattr(match, attr):
            value = getattr(match, attr)
            if value:
                decision = value
                break

    team_name = _safe_team_name(toss_team)

    # Preferred subtitle format requested by user:
    # "RCB elected to Bat"
    if toss_team and decision:
        return f"{team_name} elected to {_normalize_toss_decision(decision)}"

    if toss_team:
        return f"{team_name} won the toss"

    return "Match starting soon"


def _get_match_status_text(match, innings):
    """
    Live status text:
    - Before innings exists: toss info
    - 1st innings: toss subtitle
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

    # Use stored result if present
    for attr in ["result_text", "result", "match_result", "note"]:
        if hasattr(match, attr):
            value = getattr(match, attr)
            if isinstance(value, str) and value.strip():
                return value.strip()

    innings_list = (
        db.query(models.MatchInnings)
        .filter(models.MatchInnings.match_id == match.id)
        .order_by(models.MatchInnings.innings_no.asc())
        .all()
    )

    if len(innings_list) < 2:
        return "Match completed"

    first = innings_list[0]
    second = innings_list[1]

    first_runs = getattr(first, "runs", 0) or 0
    second_runs = getattr(second, "runs", 0) or 0
    second_wickets = getattr(second, "wickets", 0) or 0
    target = getattr(second, "target", first_runs + 1)

    team1 = match.team1 if hasattr(match, "team1") else getattr(match, "teamA", None)
    team2 = match.team2 if hasattr(match, "team2") else getattr(match, "teamB", None)

    # Chasing team wins
    if second_runs >= target:
        wickets_remaining = max(0, 10 - second_wickets)
        return f"{_safe_team_name(team2)} won by {wickets_remaining} wickets"

    # Defending team wins
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
            "runs": getattr(b, "runs", 0) or 0,
            "balls": getattr(b, "balls", 0) or 0,
        }
        for b in batsmen
    ]


def _serialize_current_bowler(db: Session, innings):
    """
    Returns current bowler statistics using your existing Bowler model.
    Compatible with your models.py where:
      - model = models.Bowler
      - stats are stored in bowlers table
      - innings has no current_bowler_id field
    """
    if not innings:
        return None

    # Get latest bowler record for this innings.
    # Prefer the bowler with most balls bowled, then latest updated row.
    bowler = (
        db.query(models.Bowler)
        .filter(models.Bowler.innings_id == innings.id)
        .order_by(
            models.Bowler.balls.desc(),
            models.Bowler.overs.desc(),
            models.Bowler.runs.asc()
        )
        .first()
    )

    if not bowler:
        return None

    # Resolve player name
    player = None
    if getattr(bowler, "player_id", None):
        player = (
            db.query(models.Player)
            .filter(models.Player.id == bowler.player_id)
            .first()
        )

    # Name priority:
    # Player.name -> Bowler.name -> Unknown Bowler
    name = (
        _safe_player_name(player)
        if player
        else (getattr(bowler, "name", None) or "Unknown Bowler")
    )

    # Read stored values
    overs = getattr(bowler, "overs", "0.0") or "0.0"
    maidens = getattr(bowler, "maidens", 0) or 0
    runs = getattr(bowler, "runs", 0) or 0
    wickets = getattr(bowler, "wickets", 0) or 0

    # Use stored economy if available, otherwise calculate from balls
    stored_economy = getattr(bowler, "economy", None)

    if stored_economy is not None:
        try:
            economy = float(stored_economy)
        except Exception:
            economy = 0.0
    else:
        total_balls = getattr(bowler, "balls", 0) or 0
        if total_balls > 0:
            economy = round((runs * 6) / total_balls, 1)
        else:
            economy = 0.0

    return {
        "name": name,
        "overs": str(overs),
        "maidens": maidens,
        "runs": runs,
        "wickets": wickets,
        "economy": f"{economy:.1f}",
    }


def _get_last_over(db: Session, innings):
    """
    Returns last up to 6 balls using your existing Ball model.

    Examples:
        ["1", "4", "0", "W", "6"]
        ["Wd", "1", "4", "W", "Nb", "6"]
    """
    if not innings:
        return []

    balls = (
        db.query(models.Ball)
        .filter(models.Ball.innings_id == innings.id)
        .order_by(
            models.Ball.created_at.desc(),
            models.Ball.over.desc(),
            models.Ball.ball.desc()
        )
        .limit(6)
        .all()
    )

    if not balls:
        return []

    # Show in chronological order (oldest -> newest)
    balls = list(reversed(balls))

    result = []

    for ball in balls:
        # Wicket takes priority
        if getattr(ball, "is_wicket", False):
            result.append("W")
            continue

        extra_type = getattr(ball, "extra_type", None)
        extra_runs = getattr(ball, "extra_runs", 0) or 0
        runs = getattr(ball, "runs", 0) or 0

        # Wide
        if extra_type and str(extra_type).upper() in ["WD", "WIDE"]:
            label = "Wd"
            if extra_runs > 1:
                label = f"Wd{extra_runs}"
            result.append(label)
            continue

        # No Ball
        if extra_type and str(extra_type).upper() in ["NB", "NOBALL", "NO_BALL"]:
            if runs > 0:
                result.append(f"Nb+{runs}")
            else:
                result.append("Nb")
            continue

        # Bye / Leg Bye
        if extra_type and str(extra_type).upper() in ["B", "BYE"]:
            result.append(f"B{extra_runs}" if extra_runs > 0 else "B")
            continue

        if extra_type and str(extra_type).upper() in ["LB", "LEG_BYE", "LEGBYE"]:
            result.append(f"LB{extra_runs}" if extra_runs > 0 else "LB")
            continue

        # Normal delivery
        total = runs + extra_runs
        result.append(str(total))

    return result

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

    team1 = match.team1 if hasattr(match, "team1") else getattr(match, "teamA", None)
    team2 = match.team2 if hasattr(match, "team2") else getattr(match, "teamB", None)

    max_overs = _get_max_overs(match)

    # ---------------------------------------------------------------
    # UPCOMING / NOT STARTED
    # ---------------------------------------------------------------
    if not innings:
        return {
            "match_id": str(match.id),
            "status": "upcoming",
            "subtitle": _get_toss_info(match),
            "team1": _safe_team_name(team1),
            "team2": _safe_team_name(team2),
            "score": None,
            "overs": None,
            "display_score": None,
            "target": None,
            "innings": None,
            "max_overs": max_overs,
            "batsmen": [],
        }

    # ---------------------------------------------------------------
    # LIVE
    # ---------------------------------------------------------------
    runs = getattr(innings, "runs", 0) or 0
    wickets = getattr(innings, "wickets", 0) or 0
    overs = getattr(innings, "overs", "0.0")

    # return {
    #     "match_id": str(match.id),
    #     "status": "live",
    #
    #     # Teams
    #     "team1": _safe_team_name(team1),
    #     "team2": _safe_team_name(team2),
    #
    #     # Score
    #     "score": _format_score(runs, wickets),
    #     "overs": overs,
    #     "max_overs": max_overs,
    #
    #     # Professional score format
    #     "display_score": _format_score_with_overs(
    #         runs,
    #         wickets,
    #         overs,
    #         max_overs,
    #     ),
    #
    #     # Additional
    #     "target": getattr(innings, "target", None),
    #     "innings": getattr(innings, "innings_no", 1),
    #
    #     # Proper subtitle:
    #     # "RCB elected to Bat"
    #     # or "Target: 156 runs"
    #     "subtitle": _get_match_status_text(match, innings),
    #
    #     # Live batsmen
    #     "batsmen": _serialize_batsmen(db, innings),
    # }

    return {
        "match_id": str(match.id),
        "status": "live",

        # Teams
        "team1": _safe_team_name(team1),
        "team2": _safe_team_name(team2),

        # Score
        "score": _format_score(runs, wickets),  # e.g. "7/0"
        "overs": overs,  # e.g. "0.2"
        "max_overs": max_overs,  # e.g. 1

        # Professional display score
        "display_score": _format_score_with_overs(
            runs,
            wickets,
            overs,
            max_overs,
        ),  # e.g. "7/0 (0.2/1)"

        # Match metadata
        "target": getattr(innings, "target", None),
        "innings": getattr(innings, "innings_no", 1),

        # Status subtitle
        # 1st innings: "SRH elected to Bat"
        # 2nd innings: "Target: 156 runs"
        "subtitle": _get_match_status_text(match, innings),

        # Live batting table
        "batsmen": _serialize_batsmen(db, innings),

        # Current bowler card
        "bowler": _serialize_current_bowler(db, innings),

        # Recent balls section
        "last_over": _get_last_over(db, innings),
    }


# ===================================================================
# UPCOMING MATCHES
# ===================================================================

@router.get("/upcoming")
def upcoming_matches(db: Session = Depends(get_db)):
    matches = (
        db.query(models.Match)
        .filter(
            func.lower(models.Match.status).in_(
                ["scheduled", "upcoming", "not_started"]
            )
        )
        .order_by(models.Match.created_at.desc())
        .all()
    )

    result = []

    for match in matches:
        team1 = match.team1 if hasattr(match, "team1") else getattr(match, "teamA", None)
        team2 = match.team2 if hasattr(match, "team2") else getattr(match, "teamB", None)

        result.append({
            "match_id": str(match.id),
            "team1": _safe_team_name(team1),
            "team2": _safe_team_name(team2),
            "overs": _get_max_overs(match),
            "max_overs": _get_max_overs(match),
            "subtitle": _get_toss_info(match),
            "status": "upcoming",
        })

    return result


# ===================================================================
# COMPLETED MATCHES
# ===================================================================

@router.get("/completed")
def completed_matches(db: Session = Depends(get_db)):
    matches = (
        db.query(models.Match)
        .filter(
            func.lower(models.Match.status).in_(
                ["completed", "finished", "ended"]
            )
        )
        .order_by(models.Match.created_at.desc())
        .all()
    )

    result = []

    for match in matches:
        team1 = match.team1 if hasattr(match, "team1") else getattr(match, "teamA", None)
        team2 = match.team2 if hasattr(match, "team2") else getattr(match, "teamB", None)

        result.append({
            "match_id": str(match.id),
            "team1": _safe_team_name(team1),
            "team2": _safe_team_name(team2),
            "overs": _get_max_overs(match),
            "max_overs": _get_max_overs(match),
            "result": _calculate_result_text(db, match),
            "status": "completed",
        })

    return result