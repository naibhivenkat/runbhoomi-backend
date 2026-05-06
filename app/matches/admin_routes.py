from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.database import models

from app.matches.match_service import resolve_match

router = APIRouter(prefix="/admin")


@router.post("/{match_id}/assign")
def assign_admin(
        match_id: str,
        admin_id: str,
        db: Session = Depends(get_db)
):
    match = resolve_match(db, match_id)

    admin = db.query(models.Player).get(admin_id)

    if not admin:
        raise HTTPException(404, "Admin not found")

    match.admin_id = admin.id

    db.commit()

    return {
        "message": "Admin assigned"
    }


@router.post("/{match_id}/start-live")
def force_live(
        match_id: str,
        db: Session = Depends(get_db)
):
    match = resolve_match(db, match_id)

    match.status = "live"

    db.commit()

    return {
        "message": "Match is live"
    }


@router.post("/{match_id}/complete")
def complete_match(
        match_id: str,
        db: Session = Depends(get_db)
):
    match = resolve_match(db, match_id)

    match.status = "completed"

    db.commit()

    return {
        "message": "Match manually completed"
    }