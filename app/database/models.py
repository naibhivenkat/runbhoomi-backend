from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey, Date
from sqlalchemy.orm import relationship
from app.database.db import Base


# =========================
# 🏏 TEAM
# =========================
class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True)
    name = Column(String)

    captain_id = Column(Integer, ForeignKey("players.id"))

    players = relationship("TeamPlayer", back_populates="team")
    captain = relationship(
        "Player",
        foreign_keys=[captain_id]
    )


# =========================
# 👤 PLAYER
# =========================
class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String(100), nullable=False)
    phone = Column(String(15), nullable=False)
    email = Column(String(120), unique=True, index=True, nullable=False)
    gender = Column(String(10), nullable=True)

    city = Column(String, nullable=True, index=True)
    role = Column(String, nullable=True, index=True)

    batting_style = Column(String, nullable=True)
    bowling_style = Column(String, nullable=True)

    experience = Column(Integer, default=0)
    jersey_number = Column(Integer, default=0)

    dob = Column(Date, nullable=True)

    password_hash = Column(String, nullable=False)
    profile_photo = Column(String, nullable=True)

    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    team = relationship(
        "Team",
        foreign_keys=[team_id]
    )
    squads = relationship("TeamPlayer", back_populates="player")


# =========================
# 🔗 TEAM PLAYER (SQUAD)
# =========================
class TeamPlayer(Base):
    __tablename__ = "team_players"

    id = Column(Integer, primary_key=True)
    team_id = Column(Integer, ForeignKey("teams.id"))
    player_id = Column(Integer, ForeignKey("players.id"))

    team = relationship("Team", back_populates="players")
    player = relationship("Player", back_populates="squads")


# =========================
# 🏏 MATCH
# =========================
class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True)

    team_a_id = Column(Integer, ForeignKey("teams.id"))
    team_b_id = Column(Integer, ForeignKey("teams.id"))

    teamA = relationship("Team", foreign_keys=[team_a_id])
    teamB = relationship("Team", foreign_keys=[team_b_id])

    status = Column(String, default="scheduled")

    # ⚠️ NOT USED FOR LIVE (kept for compatibility)
    scoreA = Column("score_a", String, nullable=True)
    scoreB = Column("score_b", String, nullable=True)
    oversA = Column("overs_a", String, nullable=True)
    oversB = Column("overs_b", String, nullable=True)

    total_overs = Column(Integer, default=20)
    current_innings = Column(Integer, default=1)

    note = Column(String)

    created_at = Column(DateTime, default=datetime.utcnow)

    playing_xi = relationship("PlayingXI", back_populates="match")


# =========================
# 🔥 PLAYING XI
# =========================
class PlayingXI(Base):
    __tablename__ = "playing_xi"

    id = Column(Integer, primary_key=True)

    match_id = Column(Integer, ForeignKey("matches.id"))
    player_id = Column(Integer, ForeignKey("players.id"))
    team_id = Column(Integer, ForeignKey("teams.id"))

    match = relationship("Match", back_populates="playing_xi")
    player = relationship("Player")
    team = relationship("Team")


# =========================
# 🧑‍🤝‍🧑 BATSMAN
# =========================
class Batsman(Base):
    __tablename__ = "batsmen"

    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey("matches.id"))

    name = Column(String)

    runs = Column(Integer, default=0)
    balls = Column(Integer, default=0)
    fours = Column(Integer, default=0)
    sixes = Column(Integer, default=0)

    is_striker = Column(Boolean, default=False)
    is_out = Column(Boolean, default=False)


# =========================
# 🎯 BOWLER
# =========================
class Bowler(Base):
    __tablename__ = "bowlers"

    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey("matches.id"))

    name = Column(String)

    overs = Column(String)
    runs = Column(Integer, default=0)
    wickets = Column(Integer, default=0)
    economy = Column(Float, default=0)


# =========================
# ⚾ BALL (CORE ENGINE)
# =========================
class Ball(Base):
    __tablename__ = "balls"

    id = Column(Integer, primary_key=True)

    match_id = Column(Integer, ForeignKey("matches.id"))

    innings = Column(Integer, default=1)

    over = Column(Integer, nullable=False)
    ball = Column(Integer, nullable=False)

    runs = Column(Integer, default=0)
    extra_type = Column(String, nullable=True)
    extra_runs = Column(Integer, default=0)

    is_wicket = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)


# =========================
# 🏆 TOURNAMENT
# =========================
class Tournament(Base):
    __tablename__ = "tournaments"

    id = Column(Integer, primary_key=True)

    name = Column(String, nullable=False)
    city = Column(String)
    ground = Column(String)

    organizer_name = Column(String)
    organizer_phone = Column(String)
    organizer_email = Column(String)

    start_date = Column(String)
    end_date = Column(String)

    category = Column(String)  # local / corporate / college
    ball_type = Column(String)  # tennis / leather
    pitch_type = Column(String)  # turf / matting
    match_type = Column(String)  # t20 / 100 / test

    total_teams = Column(Integer)

    logo_url = Column(String)

    created_at = Column(DateTime, default=datetime.utcnow)
    teams = relationship("TournamentTeam", back_populates="tournament")
    banner_url = Column(String)


# =========================
# 🔗 TOURNAMENT TEAMS
# =========================
class TournamentTeam(Base):
    __tablename__ = "tournament_teams"

    id = Column(Integer, primary_key=True)

    tournament_id = Column(Integer, ForeignKey("tournaments.id"))
    team_id = Column(Integer, ForeignKey("teams.id"))

    status = Column(String, default="pending")  # pending / approved

    tournament = relationship("Tournament", back_populates="teams")
    team = relationship("Team")


class TournamentMatch(Base):
    __tablename__ = "tournament_matches"

    id = Column(Integer, primary_key=True)

    tournament_id = Column(Integer)
    team_a = Column(String)
    team_b = Column(String)

    match_date = Column(String)
    stage = Column(String)  # league / semi / final

    winner = Column(String, nullable=True)


class TournamentPoints(Base):
    __tablename__ = "tournament_points"

    id = Column(Integer, primary_key=True)

    tournament_id = Column(Integer)
    team_name = Column(String)

    played = Column(Integer, default=0)
    wins = Column(Integer, default=0)
    losses = Column(Integer, default=0)

    runs_scored = Column(Integer, default=0)
    overs_faced = Column(Float, default=0)

    runs_conceded = Column(Integer, default=0)
    overs_bowled = Column(Float, default=0)

    points = Column(Integer, default=0)
