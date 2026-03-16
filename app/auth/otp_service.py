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

    try:


        logger.info(f"SENDINBLUE_API_KEY: {SENDINBLUE_API_KEY}")
        logger.info(f"FROM_EMAIL: {FROM_EMAIL}")

        url = "https://api.sendinblue.com/v3/smtp/email"

        headers = {
            "api-key": SENDINBLUE_API_KEY,
            "Content-Type": "application/json"
        }

        subject = "RunBhoomi Email Verification"

        html_content = f"""
        <div style="font-family: Arial, sans-serif; padding:20px;">
            <h2>RunBhoomi Verification</h2>
            <p>Your OTP is:</p>

            <div style="background:#f4f4f4;padding:20px;border-radius:8px;text-align:center;">
                <h1 style="letter-spacing:6px;">{otp}</h1>
            </div>

            <p>This OTP is valid for 2 minutes.</p>

            <p>If you didn't request this, ignore this email.</p>
        </div>
        """

        data = {
            "sender": {
                "name": "RunBhoomi",
                "email": FROM_EMAIL
            },
            "to": [{"email": email}],
            "subject": subject,
            "htmlContent": html_content
        }

        response = requests.post(url, headers=headers, json=data)

        logger.info(f"[BREVO RESPONSE] {response.status_code} {response.text}")

        return response.status_code in (200, 201)

    except Exception as e:

        logger.error(f"OTP email send failed: {e}")

        return False