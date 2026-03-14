from celery import Celery
from app.config import settings

celery = Celery("runbhoomi", broker=settings.REDIS_URL)

@celery.task
def generate_commentary(ball_id):
    print("Generating commentary for ball", ball_id)

@celery.task
def detect_highlight(ball_id):
    print("Checking highlight for ball", ball_id)
