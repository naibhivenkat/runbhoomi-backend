import random
import time
from sqlalchemy.orm import Session
from app.database import models


def generate_otp():
    return str(random.randint(100000, 999999))


def save_otp(db: Session, email: str, otp: str):

    expiry = int(time.time()) + 120

    record = db.query(models.EmailOTP).filter(models.EmailOTP.email == email).first()

    if record:
        record.otp = otp
        record.expiry = expiry
        record.attempts = 0
    else:
        record = models.EmailOTP(
            email=email,
            otp=otp,
            expiry=expiry,
            attempts=0
        )
        db.add(record)

    db.commit()


def get_otp(db: Session, email: str):

    return db.query(models.EmailOTP).filter(models.EmailOTP.email == email).first()


def delete_otp(db: Session, email: str):

    record = db.query(models.EmailOTP).filter(models.EmailOTP.email == email).first()

    if record:
        db.delete(record)
        db.commit()


def increment_attempt(db: Session, record):

    record.attempts += 1
    db.commit()