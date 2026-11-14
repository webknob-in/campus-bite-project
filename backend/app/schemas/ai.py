from datetime import datetime

from pydantic import BaseModel, StringConstraints
from typing_extensions import Annotated


class AIQuestionIn(BaseModel):
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class AIAnswerOut(BaseModel):
    answer: str
    order_count: int
    generated_at: datetime
