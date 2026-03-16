import os
import random
import time
from sqlalchemy.orm import Session
from app.database import models
import requests


SENDINBLUE_API_KEY = os.getenv("SENDINBLUE_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL")

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

def send_email_otp(email, otp):

    url = "https://api.brevo.com/v3/smtp/email"

    payload = {
        "sender": {
            "name": "RunBhoomi",
            "email": FROM_EMAIL
        },
        "to": [{"email": email}],
        "subject": "RunBhoomi OTP Verification",
        "htmlContent": f"""
        <h2>RunBhoomi Email Verification</h2>
        <p>Your OTP is:</p>
        <h1>{otp}</h1>
        <p>OTP expires in 2 minutes.</p>
        """
    }

    headers = {
        "accept": "application/json",
        "api-key": SENDINBLUE_API_KEY,
        "content-type": "application/json"
    }

    r = requests.post(url, json=payload, headers=headers)

    return r.status_code == 201