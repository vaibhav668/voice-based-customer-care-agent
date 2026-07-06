from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.database.models.booking import Booking
from app.database.models.trip import Trip
from app.repositories.base_repository import BaseRepository


class TripRepository(BaseRepository):

    def get_by_id(self, trip_id):
        stmt = (
            select(Trip)
            .where(Trip.id == trip_id)
        )

        return self.db.scalar(stmt)

    def get_trip_by_booking_code(self, booking_code: str):

        stmt = (
            select(Booking)
            .options(
                joinedload(Booking.trip).joinedload(Trip.route),
                joinedload(Booking.trip).joinedload(Trip.bus),
            )
            .where(
                Booking.booking_code == booking_code
            )
        )

        return self.db.scalar(stmt)
    
    def get_current_location(self, booking_code: str):

        stmt = (
          select(Booking)
          .options(
             joinedload(Booking.trip)
          )
          .where(
            Booking.booking_code == booking_code
          )
        )

        booking = self.db.execute(stmt).scalar_one_or_none()

        if booking is None:
           return None

        return booking.trip

    def find_trip_by_route(self, source_city: str, destination_city: str):
        from app.database.models.route import Route
        from app.database.models.bus import Bus
        from datetime import datetime, timedelta

        # 1. Search for existing trip with matching route cities
        stmt = (
            select(Trip)
            .join(Route)
            .where(
                Route.source_city.ilike(f"%{source_city}%"),
                Route.destination_city.ilike(f"%{destination_city}%"),
            )
        )
        trip = self.db.scalar(stmt)
        if trip:
            return trip

        # 2. Check if route exists or create specific route for requested cities
        stmt_route = select(Route).where(
            Route.source_city.ilike(f"%{source_city}%"),
            Route.destination_city.ilike(f"%{destination_city}%"),
        )
        route = self.db.scalar(stmt_route)
        if not route:
            route = Route(
                source_city=source_city.title(),
                destination_city=destination_city.title(),
                distance_km=600,
                estimated_duration_minutes=540,
            )
            self.db.add(route)
            self.db.flush()

        bus = self.db.scalar(select(Bus))
        if not bus:
            bus = Bus(
                bus_number="BUS-700",
                bus_name="Volvo Express Multi-Axle",
                registration_number="DL-01-AB-1234",
                capacity=40,
            )
            self.db.add(bus)
            self.db.flush()

        new_trip = Trip(
            route_id=route.id,
            bus_id=bus.id,
            departure_time=datetime.now() + timedelta(days=1),
            arrival_time=datetime.now() + timedelta(days=1, hours=9),
            status="SCHEDULED",
            available_seats=38,
        )
        self.db.add(new_trip)
        self.db.commit()
        self.db.refresh(new_trip)
        return new_trip

    