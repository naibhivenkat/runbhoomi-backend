from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.database.models import TournamentUser

# def require_admin(db: Session, user_id: int, tournament_id: int):
#     record = db.query(TournamentUser).filter_by(
#         tournament_id=tournament_id,
#         user_id=user_id
#     ).first()
#
#     if not record or record.role != "ADMIN":
#         raise HTTPException(status_code=403, detail="Admin access required")

def require_admin(db, user_id, tournament_id):
    print("USER FROM TOKEN:", user_id)

    record = db.query(TournamentUser).filter_by(
        tournament_id=tournament_id,
        user_id=user_id
    ).first()

    print("DB RECORD:", record)

    if not record or record.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Only admin allowed")