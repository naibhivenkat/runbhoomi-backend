import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    DATABASE_URL = os.getenv("DATABASE_URL","postgresql://postgres:password@localhost/runbhoomi")
    REDIS_URL = os.getenv("REDIS_URL","redis://localhost:6379")
    JWT_SECRET = os.getenv("JWT_SECRET","runbhoomi_secret")

settings = Settings()
