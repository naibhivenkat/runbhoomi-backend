from pydantic import BaseModel


class BallInput(BaseModel):
    runs: int = 0
    wicket: bool = False
    extra_type: str | None = None
    extra_runs: int = 0
    next_batsman_id: int | None = None
