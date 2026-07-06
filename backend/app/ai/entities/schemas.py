from pydantic import BaseModel


class ExtractedEntities(BaseModel):

    booking_code: str | None = None

    passenger_name: str | None = None

    complaint: str | None = None

    bus_number: str | None = None