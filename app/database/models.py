import uuid
from datetime import datetime
from sqlalchemy import UniqueConstraint
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Float,
    DateTime,
    ForeignKey,
    Date,
)

from sqlalchemy.orm import relationship

from app.database.db import Base


# =========================================================
# UUID
# =========================================================

def generate_uuid():
    return str(uuid.uuid4())


# =========================================================
# TEAM
# =========================================================

class Team(Base):
    __tablename__ = "teams"

    id = Column(String, primary_key=True, default=generate_uuid)

    name = Column(String)

    captain_id = Column(
        String,
        ForeignKey("players.id")
    )

    captain = relationship(
        "Player",
        foreign_keys=[captain_id]
    )

    players = relationship(
        "TeamPlayer",
        back_populates="team",
        cascade="all, delete-orphan"
    )


# =========================================================
# PLAYER
# =========================================================

class Player(Base):
    __tablename__ = "players"

    id = Column(
        String,
        primary_key=True,
        default=generate_uuid,
        index=True
    )

    name = Column(String(100), nullable=False)

    email = Column(
        String(120),
        unique=True,
        nullable=True
    )

    password_hash = Column(String, nullable=True)

    phone = Column(String(15), nullable=True)

    gender = Column(String(10), nullable=True)

    city = Column(
        String,
        nullable=True,
        index=True
    )

    role = Column(
        String,
        nullable=True,
        index=True
    )

    batting_style = Column(String, nullable=True)

    bowling_style = Column(String, nullable=True)

    experience = Column(Integer, default=0)

    jersey_number = Column(Integer, default=0)

    dob = Column(Date, nullable=True)

    profile_photo = Column(String, nullable=True)

    team_id = Column(
        String,
        ForeignKey("teams.id"),
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    team = relationship(
        "Team",
        foreign_keys=[team_id]
    )

    squads = relationship(
        "TeamPlayer",
        back_populates="player"
    )

    team_memberships = relationship(
        "TeamPlayer",
        back_populates="player"
    )


# =========================================================
# EMAIL OTP
# =========================================================

class EmailOTP(Base):
    __tablename__ = "email_otps"

    id = Column(
        String,
        primary_key=True,
        default=generate_uuid,
        index=True
    )

    email = Column(String, index=True)

    otp = Column(String)

    expiry = Column(Integer)

    attempts = Column(Integer, default=0)

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )


# =========================================================
# TEAM PLAYER
# =========================================================

class TeamPlayer(Base):
    __tablename__ = "team_players"

    id = Column(
        String,
        primary_key=True,
        default=generate_uuid
    )

    team_id = Column(
        String,
        ForeignKey("teams.id"),
        nullable=False
    )

    player_id = Column(
        String,
        ForeignKey("players.id"),
        nullable=False
    )

    role = Column(String, default="PLAYER")

    player_type = Column(
        String,
        default="Batsman"
    )

    is_captain = Column(
        Boolean,
        default=False
    )

    is_vc = Column(
        Boolean,
        default=False
    )

    is_wk = Column(
        Boolean,
        default=False
    )

    team = relationship(
        "Team",
        back_populates="players"
    )

    player = relationship(
        "Player",
        back_populates="squads"
    )

    __table_args__ = (
        UniqueConstraint(
            "team_id",
            "player_id",
            name="uq_team_player"
        ),
    )


# =========================================================
# MATCH
# =========================================================

# class Match(Base):
#     __tablename__ = "matches"
#
#     # =====================================================
#     # CORE
#     # =====================================================
#
#     id = Column(
#         String,
#         primary_key=True,
#         default=generate_uuid
#     )
#
#     team_a_id = Column(
#         String,
#         ForeignKey("teams.id"),
#         nullable=False
#     )
#
#     team_b_id = Column(
#         String,
#         ForeignKey("teams.id"),
#         nullable=False
#     )
#
#     teamA = relationship(
#         "Team",
#         foreign_keys=[team_a_id]
#     )
#
#     teamB = relationship(
#         "Team",
#         foreign_keys=[team_b_id]
#     )
#
#     tournament_id = Column(
#         String,
#         ForeignKey("tournaments.id"),
#         nullable=True
#     )
#
#     fixture_id = Column(String, nullable=True)
#
#     admin_id = Column(
#         String,
#         ForeignKey("players.id"),
#         nullable=True
#     )
#
#     # =====================================================
#     # MATCH STATE
#     # =====================================================
#
#     status = Column(
#         String,
#         default="scheduled"
#     )
#     # scheduled
#     # live
#     # innings_break
#     # completed
#
#     total_overs = Column(Integer, default=20)
#
#     current_innings = Column(Integer, default=1)
#
#     # =====================================================
#     # TOSS
#     # =====================================================
#
#     toss_winner_team_id = Column(
#         String,
#         ForeignKey("teams.id"),
#         nullable=True
#     )
#
#     toss_decision = Column(String, nullable=True)
#     # bat / bowl
#
#     # =====================================================
#     # RESULT
#     # =====================================================
#
#     target = Column(Integer, nullable=True)
#
#     winner_team_id = Column(
#         String,
#         ForeignKey("teams.id"),
#         nullable=True
#     )
#
#     result = Column(String, nullable=True)
#
#     note = Column(String, nullable=True)
#
#     created_at = Column(
#         DateTime,
#         default=datetime.utcnow
#     )
#
#     # =====================================================
#     # RELATIONSHIPS
#     # =====================================================
#
#     playing_xi = relationship(
#         "PlayingXI",
#         back_populates="match",
#         cascade="all, delete-orphan"
#     )
#
#     innings = relationship(
#         "MatchInnings",
#         back_populates="match",
#         cascade="all, delete-orphan"
#     )
#
#     balls = relationship(
#         "Ball",
#         back_populates="match",
#         cascade="all, delete-orphan"
#     )
#
#     batsmen = relationship(
#         "Batsman",
#         back_populates="match",
#         cascade="all, delete-orphan"
#     )
#
#     bowlers = relationship(
#         "Bowler",
#         back_populates="match",
#         cascade="all, delete-orphan"
#     )
#

# =========================================================
# MATCH INNINGS
# =========================================================


# =========================================================
# MATCH
# =========================================================

class Match(Base):
    __tablename__ = "matches"

    id = Column(
        String,
        primary_key=True,
        default=generate_uuid
    )

    team_a_id = Column(
        String,
        ForeignKey("teams.id"),
        nullable=False
    )

    team_b_id = Column(
        String,
        ForeignKey("teams.id"),
        nullable=False
    )

    # -----------------------------------------------------
    # TEAM RELATIONSHIPS
    # -----------------------------------------------------
    teamA = relationship(
        "Team",
        foreign_keys=[team_a_id]
    )

    teamB = relationship(
        "Team",
        foreign_keys=[team_b_id]
    )

    # Aliases used by live_routes.py
    team1 = relationship(
        "Team",
        foreign_keys=[team_a_id],
        viewonly=True
    )

    team2 = relationship(
        "Team",
        foreign_keys=[team_b_id],
        viewonly=True
    )

    tournament_id = Column(
        String,
        ForeignKey("tournaments.id"),
        nullable=True
    )

    fixture_id = Column(String, nullable=True)

    admin_id = Column(
        String,
        ForeignKey("players.id"),
        nullable=True
    )

    # -----------------------------------------------------
    # MATCH STATE
    # -----------------------------------------------------
    status = Column(
        String,
        default="scheduled"
    )

    total_overs = Column(Integer, default=20)

    current_innings = Column(Integer, default=1)

    # -----------------------------------------------------
    # TOSS
    # -----------------------------------------------------
    toss_winner_team_id = Column(
        String,
        ForeignKey("teams.id"),
        nullable=True
    )

    toss_decision = Column(String, nullable=True)

    # IMPORTANT RELATIONSHIP REQUIRED FOR LIVE API
    toss_winner_team = relationship(
        "Team",
        foreign_keys=[toss_winner_team_id]
    )

    # -----------------------------------------------------
    # RESULT
    # -----------------------------------------------------
    target = Column(Integer, nullable=True)

    winner_team_id = Column(
        String,
        ForeignKey("teams.id"),
        nullable=True
    )

    result = Column(String, nullable=True)

    note = Column(String, nullable=True)

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    # -----------------------------------------------------
    # RELATIONSHIPS
    # -----------------------------------------------------
    playing_xi = relationship(
        "PlayingXI",
        back_populates="match",
        cascade="all, delete-orphan"
    )

    innings = relationship(
        "MatchInnings",
        back_populates="match",
        cascade="all, delete-orphan"
    )

    balls = relationship(
        "Ball",
        back_populates="match",
        cascade="all, delete-orphan"
    )

    batsmen = relationship(
        "Batsman",
        back_populates="match",
        cascade="all, delete-orphan"
    )

    bowlers = relationship(
        "Bowler",
        back_populates="match",
        cascade="all, delete-orphan"
    )


class MatchInnings(Base):
    __tablename__ = "match_innings"

    id = Column(
        String,
        primary_key=True,
        default=generate_uuid
    )

    match_id = Column(
        String,
        ForeignKey("matches.id"),
        nullable=False
    )

    innings_no = Column(Integer, nullable=False)

    batting_team_id = Column(
        String,
        ForeignKey("teams.id"),
        nullable=False
    )

    bowling_team_id = Column(
        String,
        ForeignKey("teams.id"),
        nullable=False
    )

    runs = Column(Integer, default=0)

    wickets = Column(Integer, default=0)

    overs = Column(String, default="0.0")

    target = Column(Integer, nullable=True)

    status = Column(
        String,
        default="live"
    )
    # live / completed

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    match = relationship(
        "Match",
        back_populates="innings"
    )

    balls = relationship(
        "Ball",
        cascade="all, delete-orphan"
    )

    batsmen = relationship(
        "Batsman",
        cascade="all, delete-orphan"
    )

    bowlers = relationship(
        "Bowler",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint(
            "match_id",
            "innings_no",
            name="uq_match_innings"
        ),
    )


# =========================================================
# PLAYING XI
# =========================================================

class PlayingXI(Base):
    __tablename__ = "playing_xi"

    id = Column(
        String,
        primary_key=True,
        default=generate_uuid
    )

    match_id = Column(
        String,
        ForeignKey("matches.id")
    )

    player_id = Column(
        String,
        ForeignKey("players.id")
    )

    team_id = Column(
        String,
        ForeignKey("teams.id")
    )

    match = relationship(
        "Match",
        back_populates="playing_xi"
    )

    player = relationship("Player")

    team = relationship("Team")


# =========================================================
# BATSMAN
# =========================================================

class Batsman(Base):
    __tablename__ = "batsmen"

    id = Column(
        String,
        primary_key=True,
        default=generate_uuid
    )

    match_id = Column(
        String,
        ForeignKey("matches.id")
    )

    innings_id = Column(
        String,
        ForeignKey("match_innings.id"),
        nullable=False
    )

    player_id = Column(
        String,
        ForeignKey("players.id")
    )

    team_id = Column(
        String,
        ForeignKey("teams.id")
    )

    name = Column(String)

    runs = Column(Integer, default=0)

    balls = Column(Integer, default=0)

    fours = Column(Integer, default=0)

    sixes = Column(Integer, default=0)

    is_striker = Column(
        Boolean,
        default=False
    )

    is_out = Column(
        Boolean,
        default=False
    )

    match = relationship(
        "Match",
        back_populates="batsmen"
    )


# =========================================================
# BOWLER
# =========================================================

class Bowler(Base):
    __tablename__ = "bowlers"

    id = Column(
        String,
        primary_key=True,
        default=generate_uuid
    )

    match_id = Column(
        String,
        ForeignKey("matches.id")
    )

    innings_id = Column(
        String,
        ForeignKey("match_innings.id"),
        nullable=False
    )

    player_id = Column(
        String,
        ForeignKey("players.id")
    )

    team_id = Column(
        String,
        ForeignKey("teams.id")
    )

    name = Column(String)

    overs = Column(String, default="0.0")

    maidens = Column(Integer, default=0)

    runs = Column(Integer, default=0)

    wickets = Column(Integer, default=0)

    economy = Column(Float, default=0)

    match = relationship(
        "Match",
        back_populates="bowlers"
    )

    balls = Column(
        Integer,
        default=0
    )


# =========================================================
# BALL
# =========================================================

class Ball(Base):
    __tablename__ = "balls"

    id = Column(
        String,
        primary_key=True,
        default=generate_uuid
    )

    match_id = Column(
        String,
        ForeignKey("matches.id")
    )

    innings_id = Column(
        String,
        ForeignKey("match_innings.id"),
        nullable=False
    )

    over = Column(Integer, nullable=False)

    ball = Column(Integer, nullable=False)

    batsman_id = Column(
        String,
        ForeignKey("players.id"),
        nullable=True
    )

    non_striker_id = Column(
        String,
        ForeignKey("players.id"),
        nullable=True
    )

    bowler_id = Column(
        String,
        ForeignKey("players.id"),
        nullable=True
    )

    runs = Column(Integer, default=0)

    extra_type = Column(String, nullable=True)

    extra_runs = Column(Integer, default=0)

    is_wicket = Column(Boolean, default=False)

    wicket_type = Column(String, nullable=True)

    player_out_id = Column(
        String,
        ForeignKey("players.id"),
        nullable=True
    )

    is_legal_ball = Column(Boolean, default=True)

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    match = relationship(
        "Match",
        back_populates="balls"
    )


# =========================================================
# TOURNAMENT
# =========================================================

class Tournament(Base):
    __tablename__ = "tournaments"

    id = Column(
        String,
        primary_key=True,
        default=generate_uuid
    )

    name = Column(String, nullable=False)

    created_by = Column(
        String,
        ForeignKey("players.id")
    )

    city = Column(String)

    ground = Column(String)

    organizer_name = Column(String)

    organizer_phone = Column(String)

    organizer_email = Column(String)

    start_date = Column(String)

    end_date = Column(String)

    category = Column(String)

    ball_type = Column(String)

    pitch_type = Column(String)

    match_type = Column(String)

    total_teams = Column(Integer)

    logo_url = Column(String)

    banner_url = Column(String)

    format = Column(String, default="league")

    overs = Column(Integer, default=6)

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    teams = relationship(
        "TournamentTeam",
        back_populates="tournament"
    )


# =========================================================
# TOURNAMENT TEAM
# =========================================================

class TournamentTeam(Base):
    __tablename__ = "tournament_teams"

    __table_args__ = (
        UniqueConstraint(
            "tournament_id",
            "team_id",
            name="uq_tournament_team"
        ),
    )

    id = Column(
        String,
        primary_key=True,
        default=generate_uuid
    )

    tournament_id = Column(
        String,
        ForeignKey("tournaments.id")
    )

    team_id = Column(
        String,
        ForeignKey("teams.id")
    )

    status = Column(
        String,
        default="pending"
    )

    tournament = relationship(
        "Tournament",
        back_populates="teams"
    )

    team = relationship("Team")


# =========================================================
# TOURNAMENT MATCH
# =========================================================

class TournamentMatch(Base):
    __tablename__ = "tournament_matches"

    id = Column(
        String,
        primary_key=True,
        default=generate_uuid
    )

    tournament_id = Column(
        String,
        ForeignKey("tournaments.id")
    )

    team_a = Column(String)

    team_b = Column(String)

    match_date = Column(String)

    winner = Column(String, nullable=True)

    match_id = Column(
        String,
        ForeignKey("matches.id"),
        nullable=True
    )

    team_a_id = Column(String)

    team_b_id = Column(String)

    group_id = Column(String, nullable=True)

    match_type = Column(
        String,
        default="league"
    )

    round = Column(Integer, default=1)

    match_time = Column(String, nullable=True)


# =========================================================
# TOURNAMENT POINTS
# =========================================================

class TournamentPoints(Base):
    __tablename__ = "tournament_points"

    id = Column(
        String,
        primary_key=True,
        default=generate_uuid
    )

    tournament_id = Column(String)

    team_id = Column(
        String,
        ForeignKey("teams.id")
    )

    team = relationship("Team")

    played = Column(Integer, default=0)

    wins = Column(Integer, default=0)

    losses = Column(Integer, default=0)

    runs_scored = Column(Integer, default=0)

    overs_faced = Column(Float, default=0)

    runs_conceded = Column(Integer, default=0)

    overs_bowled = Column(Float, default=0)

    points = Column(Integer, default=0)

    ties = Column(Integer, default=0)


# =========================================================
# TOURNAMENT GROUP
# =========================================================

class TournamentGroup(Base):
    __tablename__ = "tournament_groups"

    id = Column(
        String,
        primary_key=True,
        default=generate_uuid
    )

    tournament_id = Column(
        String,
        ForeignKey("tournaments.id")
    )

    name = Column(String)


# =========================================================
# GROUP TEAM
# =========================================================

class GroupTeam(Base):
    __tablename__ = "group_teams"

    id = Column(
        String,
        primary_key=True,
        default=generate_uuid
    )

    group_id = Column(
        String,
        ForeignKey("tournament_groups.id")
    )

    team_id = Column(
        String,
        ForeignKey("teams.id")
    )


# =========================================================
# TEAM INVITE
# =========================================================

class TeamInvite(Base):
    __tablename__ = "team_invites"

    id = Column(
        String,
        primary_key=True,
        default=generate_uuid
    )

    team_id = Column(
        String,
        ForeignKey("teams.id"),
        nullable=False
    )

    code = Column(
        String(8),
        unique=True,
        nullable=False
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )


# =========================================================
# TOURNAMENT USER
# =========================================================

class TournamentUser(Base):
    __tablename__ = "tournament_users"

    id = Column(
        String,
        primary_key=True,
        default=generate_uuid
    )

    tournament_id = Column(
        String,
        ForeignKey("tournaments.id")
    )

    user_id = Column(
        String,
        ForeignKey("players.id")
    )

    role = Column(
        String,
        default="PLAYER"
    )

    tournament = relationship("Tournament")

    user = relationship("Player")


# =========================================================
# USER
# =========================================================

class User(Base):
    __tablename__ = "users"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    name = Column(String, nullable=False)

    phone = Column(
        String,
        unique=True,
        index=True,
        nullable=False
    )


# =========================================================
# TOURNAMENT OFFICIAL
# =========================================================

class TournamentOfficial(Base):
    __tablename__ = "tournament_officials"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    tournament_id = Column(
        String,
        index=True,
        nullable=False
    )

    user_id = Column(
        String,
        ForeignKey("players.id"),
        nullable=False
    )

    role = Column(String, nullable=False)

    user = relationship("Player")
