from fastapi import FastAPI
from app.database.db import engine
from app.database.models import Base

from app.auth.auth_routes import router as auth_router
from app.matches.match_routes import router as match_router
from app.matches.scoring_routes import router as scoring_router
from app.tournaments.tournament_routes import router as tournament_router

app = FastAPI(title="RunBhoomi API")

Base.metadata.create_all(bind=engine)

app.include_router(auth_router)
app.include_router(match_router)
app.include_router(scoring_router)
app.include_router(tournament_router)

@app.get("/")
def home():
    return {"status":"RunBhoomi backend running"}
