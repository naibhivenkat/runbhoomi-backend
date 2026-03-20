from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.auth.auth_routes import router as auth_router
from app.matches.match_routes import router as match_router
from app.matches.scoring_routes import router as scoring_router
from app.tournaments.tournament_routes import router as tournament_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 App starting...")

    try:
        # ✅ Import DB ONLY at runtime
        from app.database.db import engine
        from app.database.models import Base

        print("🔥 Connecting to DB...")
        Base.metadata.create_all(bind=engine)
        print("✅ DB Connected")
    except Exception as e:
        print("❌ DB ERROR:", e)

    yield

    print("🛑 App shutting down...")


app = FastAPI(
    title="RunBhoomi API",
    lifespan=lifespan
)

# Routers
app.include_router(auth_router)
app.include_router(match_router)
app.include_router(scoring_router)
app.include_router(tournament_router)

# Routes
@app.get("/")
def home():
    return {"status": "RunBhoomi backend running"}

@app.get("/health")
def health():
    return {"status": "ok"}