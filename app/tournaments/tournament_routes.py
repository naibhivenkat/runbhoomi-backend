from fastapi import APIRouter

router=APIRouter(prefix="/tournaments")

@router.get("/")
def tournaments():
    return {"message":"tournament endpoints"}
