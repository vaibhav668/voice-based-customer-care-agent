from app.database.session import SessionLocal
from app.repositories.trip_repository import TripRepository
from app.services.trip_service import TripService

db = SessionLocal()

service = TripService(
    TripRepository(db)
)

print(
    service.get_trip_from_booking(
        "BK-100001"
    )
)