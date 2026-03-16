import os
import random
import time
from sqlalchemy.orm import Session
from app.database import models
import requests
import logging

logger = logging.getLogger(__name__)

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
    print("API KEY:", SENDINBLUE_API_KEY)
    print("FROM EMAIL:", FROM_EMAIL)

    url = "https://api.sendinblue.com/v3/smtp/email"

    headers = {
        "api-key": SENDINBLUE_API_KEY,
        "Content-Type": "application/json"
    }

    data = {
        "sender": {
            "name": "RunBhoomi",
            "email": FROM_EMAIL
        },
        "to": [{"email": email}],
        "subject": "RunBhoomi OTP Verification",
        "htmlContent": f"<h2>Your OTP is {otp}</h2>"
    }

    response = requests.post(url, headers=headers, json=data)

    print("BREVO STATUS:", response.status_code)
    print("BREVO RESPONSE:", response.text)

    return response.status_code in (200, 201)