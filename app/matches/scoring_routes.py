from fastapi import APIRouter,Depends
from sqlalchemy.orm import Session
from app.database.db import get_db
from app.database import models
from app.cache.redis_client import redis_client
from app.celery_worker import generate_commentary,detect_highlight

router=APIRouter(prefix="/scoring")

@router.post("/ball")
def add_ball(match_id:int,over:int,ball:int,runs:int,db:Session=Depends(get_db)):
    b=models.Ball(match_id=match_id,over=over,ball=ball,runs=runs)
    db.add(b)
    db.commit()

    redis_client.set(f"match:{match_id}:last_ball",runs)

    generate_commentary.delay(b.id)
    detect_highlight.delay(b.id)

    return {"status":"ball saved"}
