# import os
# import random
# import time
# from sqlalchemy.orm import Session
# from app.database import models
# import requests
# import logging
#
# logger = logging.getLogger(__name__)
#
# SENDINBLUE_API_KEY = os.getenv("SENDINBLUE_API_KEY")
# FROM_EMAIL = os.getenv("FROM_EMAIL")
#
# def generate_otp():
#     return str(random.randint(100000, 999999))
#
#
# def save_otp(db: Session, email: str, otp: str):
#
#     expiry = int(time.time()) + 120
#
#     record = db.query(models.EmailOTP).filter(models.EmailOTP.email == email).first()
#
#     if record:
#         record.otp = otp
#         record.expiry = expiry
#         record.attempts = 0
#     else:
#         record = models.EmailOTP(
#             email=email,
#             otp=otp,
#             expiry=expiry,
#             attempts=0
#         )
#         db.add(record)
#
#     db.commit()
#
#
# def get_otp(db: Session, email: str):
#
#     return db.query(models.EmailOTP).filter(models.EmailOTP.email == email).first()
#
#
# def delete_otp(db: Session, email: str):
#
#     record = db.query(models.EmailOTP).filter(models.EmailOTP.email == email).first()
#
#     if record:
#         db.delete(record)
#         db.commit()
#
#
# def increment_attempt(db: Session, record):
#
#     record.attempts += 1
#     db.commit()
#
# def send_email_otp(email, otp):
#
#     url = "https://api.sendinblue.com/v3/smtp/email"
#
#     headers = {
#         "api-key": SENDINBLUE_API_KEY,
#         "Content-Type": "application/json"
#     }
#
#     data = {
#         "sender": {
#             "name": "RunBhoomi",
#             "email": FROM_EMAIL
#         },
#         "to": [{"email": email}],
#         "subject": "RunBhoomi OTP Verification",
#         "htmlContent": f"<h2>Your OTP is {otp}</h2>"
#     }
#
#     response = requests.post(url, headers=headers, json=data)
#
#
#     return response.status_code in (200, 201)
#
#
# def send_email_login_otp(email, otp):
#
#     url = "https://api.sendinblue.com/v3/smtp/email"
#
#     headers = {
#         "api-key": SENDINBLUE_API_KEY,
#         "Content-Type": "application/json"
#     }
#
#     data = {
#         "sender": {
#             "name": "RunBhoomi",
#             "email": FROM_EMAIL
#         },
#         "to": [{"email": email}],
#         "subject": "RunBhoomi Login OTP",
#         "htmlContent": f"<h2>Your OTP for Login {otp}</h2>"
#     }
#
#     response = requests.post(url, headers=headers, json=data)
#
#
#     return response.status_code in (200, 201)


import os
import random
import time
import logging
import requests
from sqlalchemy.orm import Session
from app.database import models

logger = logging.getLogger(__name__)

SENDINBLUE_API_KEY = os.getenv("SENDINBLUE_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL")


# 🔹 GENERATE OTP
def generate_otp():
    return str(random.randint(100000, 999999))


# 🔹 SAVE OTP (CREATE OR UPDATE)
def save_otp(db: Session, email: str, otp: str):
    email = email.lower().strip()
    expiry = int(time.time()) + 120  # 2 mins

    record = db.query(models.EmailOTP).filter(
        models.EmailOTP.email == email
    ).first()

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


# 🔹 GET OTP
def get_otp(db: Session, email: str):
    email = email.lower().strip()
    return db.query(models.EmailOTP).filter(
        models.EmailOTP.email == email
    ).first()


# 🔹 DELETE OTP
def delete_otp(db: Session, email: str):
    email = email.lower().strip()

    record = db.query(models.EmailOTP).filter(
        models.EmailOTP.email == email
    ).first()

    if record:
        db.delete(record)
        db.commit()


# 🔹 INCREMENT ATTEMPTS
def increment_attempt(db: Session, record):
    record.attempts += 1
    db.commit()


# 🔥 SINGLE EMAIL SENDER (REUSABLE)
def send_email_otp(email, otp, subject="RunBhoomi OTP", is_login=False):
    email = email.lower().strip()

    if not SENDINBLUE_API_KEY or not FROM_EMAIL:
        logger.error("Email config missing")
        return False

    url = "https://api.sendinblue.com/v3/smtp/email"

    headers = {
        "api-key": SENDINBLUE_API_KEY,
        "Content-Type": "application/json"
    }

    # 🔥 Dynamic content
    if is_login:
        html = f"""
        <h2>RunBhoomi Login OTP</h2>
        <p>Your OTP for login is:</p>
        <h1>{otp}</h1>
        <p>This OTP is valid for 2 minutes.</p>
        """
    else:
        html = f"""
        <h2>RunBhoomi Verification</h2>
        <p>Your OTP is:</p>
        <h1>{otp}</h1>
        <p>This OTP is valid for 2 minutes.</p>
        """

    data = {
        "sender": {
            "name": "RunBhoomi",
            "email": FROM_EMAIL
        },
        "to": [{"email": email}],
        "subject": subject,
        "htmlContent": html
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json=data,
            timeout=10  # 🔥 prevent hanging
        )

        logger.info(f"Email status: {response.status_code}")
        logger.debug(f"Email response: {response.text}")

        return response.status_code in (200, 201)

    except Exception as e:
        logger.error(f"Email sending failed: {e}")
        return False


def send_confirmation_email(email, subject="Confirmation Email"):
    email = email.lower().strip()

    if not SENDINBLUE_API_KEY or not FROM_EMAIL:
        logger.error("Email config missing")
        return False

    url = "https://api.sendinblue.com/v3/smtp/email"

    text = "Your Login Password is Changed"

    headers = {
        "api-key": SENDINBLUE_API_KEY,
        "Content-Type": "application/json"
    }
    html = f"""
    <h2>RunBhoomi Confirmation Email</h2>
    <p>Your OTP is:</p>
    <h1>{text}</h1>
    <p>Note : If your are  not changed please contact Support Team Thank You</p>
    """

    data = {
        "sender": {
            "name": "RunBhoomi",
            "email": FROM_EMAIL
        },
        "to": [{"email": email}],
        "subject": subject,
        "htmlContent": html
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json=data,
            timeout=10  # 🔥 prevent hanging
        )

        logger.info(f"Email status: {response.status_code}")
        logger.debug(f"Email response: {response.text}")

        return response.status_code in (200, 201)

    except Exception as e:
        logger.error(f"Email sending failed: {e}")
        return False
