from pydantic import BaseModel


class PlannerOutput(BaseModel):

    tool: str

    confidence: float

    booking_required: bool

    reasoning: str