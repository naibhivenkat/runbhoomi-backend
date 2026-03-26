from sqlalchemy import Column,Integer,String,Boolean,Float,DateTime, Date, BigInteger, ForeignKey
from datetime import datetime
from app.database.db import Base

class User(Base):
    __tablename__="users"
    id=Column(Integer,primary_key=True)
    name=Column(String)
    email=Column(String,unique=True)
    password_hash=Column(String)

class Team(Base):
    __tablename__="teams"
    id=Column(Integer,primary_key=True)
    name=Column(String)

class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True)

    teamA_id = Column("team_a_id", Integer, ForeignKey("teams.id"))
    teamB_id = Column("team_b_id", Integer, ForeignKey("teams.id"))

    status = Column(String)

    scoreA = Column("score_a", String)
    scoreB = Column("score_b", String)

    oversA = Column("overs_a", String)
    oversB = Column("overs_b", String)

    note = Column(String)

    created_at = Column(DateTime, default=datetime.utcnow)

class Ball(Base):
    __tablename__="balls"
    id=Column(Integer,primary_key=True)
    match_id=Column(Integer)
    over=Column(Integer)
    ball=Column(Integer)
    runs=Column(Integer)
    is_wicket=Column(Boolean)
    shot_zone=Column(String)
    pitch_x=Column(Float)
    pitch_y=Column(Float)
    created_at=Column(DateTime,default=datetime.utcnow)


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
