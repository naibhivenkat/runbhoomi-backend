from datetime import datetime

from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, Date, BigInteger, ForeignKey
from sqlalchemy.orm import relationship

from app.database.db import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String, unique=True)
    password_hash = Column(String)


class Team(Base):
    __tablename__ = "teams"
    id = Column(Integer, primary_key=True)
    name = Column(String)


class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True)

    teamA_id = Column("team_a_id", Integer, ForeignKey("teams.id"))
    teamB_id = Column("team_b_id", Integer, ForeignKey("teams.id"))

    teamA = relationship("Team", foreign_keys=[teamA_id])
    teamB = relationship("Team", foreign_keys=[teamB_id])

    status = Column(String)

    scoreA = Column("score_a", String)
    scoreB = Column("score_b", String)

    oversA = Column("overs_a", String)
    oversB = Column("overs_b", String)

    note = Column(String)

    created_at = Column(DateTime, default=datetime.utcnow)


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


class EmailOTP(Base):
    __tablename__ = "email_otp"

    email = Column(String, primary_key=True, index=True)
    otp = Column(String, nullable=False)
    expiry = Column(BigInteger, nullable=False)
    attempts = Column(Integer, default=0)


class Batsman(Base):
    __tablename__ = "batsmen"

    id = Column(Integer, primary_key=True)

    match_id = Column(Integer, ForeignKey("matches.id"))

    name = Column(String)
    runs = Column(Integer, default=0)
    balls = Column(Integer, default=0)
    fours = Column(Integer, default=0)
    sixes = Column(Integer, default=0)
    strike_rate = Column(Float, default=0)

    is_striker = Column(Boolean, default=False)
    is_out = Column(Boolean, default=False)


class Bowler(Base):
    __tablename__ = "bowlers"

    id = Column(Integer, primary_key=True)

    match_id = Column(Integer, ForeignKey("matches.id"))

    name = Column(String)
    overs = Column(String)  # "3.2"
    runs = Column(Integer)
    wickets = Column(Integer)
    economy = Column(Float)


class Ball(Base):
    __tablename__ = "balls"

    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, nullable=False)

    over = Column(Integer, nullable=False)
    ball = Column(Integer, nullable=False)  # 1 to 6 (legal balls only)

    runs = Column(Integer, default=0)  # bat runs
    extra_type = Column(String, nullable=True)  # wide, no_ball, bye, leg_bye
    extra_runs = Column(Integer, default=0)

    is_wicket = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
