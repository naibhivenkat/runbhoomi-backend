from jose import jwt
from datetime import datetime,timedelta
from app.config import settings

def create_token(user_id):
    payload={
        "user_id":user_id,
        "exp":datetime.utcnow()+timedelta(days=1)
    }
    return jwt.encode(payload,settings.JWT_SECRET)
