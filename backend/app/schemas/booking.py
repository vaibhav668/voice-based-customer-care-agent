from datetime import datetime
from pydantic import BaseModel


class BookingResponse(BaseModel):
    booking_code: str
    passenger_name: str
    seat_number: str
    booking_status: str
    payment_status: str

    bus_name: str

    source_city: str
    destination_city: str

    departure_time: datetime
    arrival_time: datetime

    trip_status: str
    delay_minutes: int