import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Local application imports
from app.auth.auth_routes import router as auth_router
from app.matches.match_routes import router as match_router
from app.matches.scoring_routes import router as scoring_router
from app.tournaments.tournament_routes import router as tournament_router

# Configure logging for production-ready output
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 App starting...")

    try:
        # ✅ Import DB ONLY at runtime to prevent circular imports
        from app.database.db import engine
        from app.database.models import Base

        logger.info("🔥 Connecting to DB...")
        Base.metadata.create_all(bind=engine)
        logger.info("✅ DB Connected successfully")
    except Exception as e:
        logger.error(f"❌ DB ERROR: {e}")

    yield

    logger.info("🛑 App shutting down...")


# Application Factory
app = FastAPI(
    title="RunBhoomi API",
    description="Backend API for the RunBhoomi offline-first cricket scoring app.",
    version="1.0.0",
    lifespan=lifespan
)

# Middleware Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Note: Restrict this to your specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router Inclusions
app.include_router(auth_router)
app.include_router(match_router)
app.include_router(scoring_router)
app.include_router(tournament_router)


# =========================
# Base & Health Routes
# =========================

@app.api_route("/", methods=["GET", "HEAD"], tags=["System"])
async def home():
    """Root endpoint to verify the API is reachable."""
    return {"status": "✅ RunBhoomi backend running 🚀"}


@app.api_route("/health", methods=["GET", "HEAD"], tags=["System"])
async def health():
    """Health check endpoint for server monitoring."""
    return {"status": "🚀 Backend is Healthy ✅✅"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)











# from fastapi import FastAPI
# from contextlib import asynccontextmanager
# from fastapi.middleware.cors import CORSMiddleware
# from app.auth.auth_routes import router as auth_router
# from app.matches.match_routes import router as match_router
# from app.matches.scoring_routes import router as scoring_router
# from app.tournaments.tournament_routes import router as tournament_router
#
#
# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     print("🚀 App starting...")
#
#     try:
#         # ✅ Import DB ONLY at runtime
#         from app.database.db import engine
#         from app.database.models import Base
#
#         print("🔥 Connecting to DB...")
#         Base.metadata.create_all(bind=engine)
#         print("✅ DB Connected")
#     except Exception as e:
#         print("❌ DB ERROR:", e)
#
#     yield
#
#     print("🛑 App shutting down...")
#
#
# app = FastAPI(
#     title="RunBhoomi API",
#     lifespan=lifespan
# )
#
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )
#
# # Routers
# app.include_router(auth_router)
# app.include_router(match_router)
# app.include_router(scoring_router)
# app.include_router(tournament_router)
#
#
# # Routes
# @app.api_route("/", methods=["GET", "HEAD"])
# def home():
#     return {"status": "✅ Run Bhoomi backend running 🚀 "}
#
#
# @app.api_route("/health", methods=["GET", "HEAD"])
# def health():
#     return {"status": "🚀 Backend is Healthy ✅✅"}
