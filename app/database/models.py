from sqlalchemy import Column,Integer,String,Boolean,Float,DateTime, Date, BigInteger
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
    __tablename__="matches"
    id=Column(Integer,primary_key=True)
    team1_id=Column(Integer)
    team2_id=Column(Integer)
    overs=Column(Integer)
    status=Column(String)

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

    name = Column(String)
    phone = Column(String)
    email = Column(String)

    city = Column(String)
    role = Column(String)

    batting_style = Column(String)
    bowling_style = Column(String)

    experience = Column(Integer)
    jersey_number = Column(Integer)

    dob = Column(Date)

    password_hash = Column(String)
    profile_photo = Column(String)   # optional
    created_at = Column(DateTime, default=datetime.utcnow)

class EmailOTP(Base):
    __tablename__ = "email_otp"

    email = Column(String, primary_key=True, index=True)
    otp = Column(String, nullable=False)
    expiry = Column(BigInteger, nullable=False)
    attempts = Column(Integer, default=0)
