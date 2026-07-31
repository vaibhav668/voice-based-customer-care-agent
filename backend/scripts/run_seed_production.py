import os
import sqlite3
import base64
import hashlib
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from datetime import datetime, timezone, timedelta
import uuid

# pgAdmin decryption logic
def decrypt_password(cipher_text, key):
    decoded = base64.b64decode(cipher_text)
    iv = decoded[:16]
    encrypted = decoded[16:]
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    decrypted = decryptor.update(encrypted) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    unpadded = unpadder.update(decrypted) + unpadder.finalize()
    return unpadded.decode('utf-8')

def get_render_url():
    db_path = os.path.expanduser(r"~\AppData\Roaming\pgAdmin\pgadmin4.db")
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"pgAdmin database not found at {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT value FROM keys WHERE name='crypto_key';")
    row = cursor.fetchone()
    if not row:
        raise ValueError("Crypto key not found in pgAdmin database.")
    crypto_key = row[0]
    aes_key = hashlib.sha256(crypto_key.encode('utf-8')).digest()

    cursor.execute("SELECT name, host, port, username, password, maintenance_db FROM server WHERE host LIKE '%render.com%';")
    servers = cursor.fetchall()
    
    if not servers:
        # Try finding by name support-ai-db
        cursor.execute("SELECT name, host, port, username, password, maintenance_db FROM server WHERE name='support-ai-db';")
        servers = cursor.fetchall()

    conn.close()

    if not servers:
        raise ValueError("Render server credentials not found in pgAdmin.")

    name, host, port, username, password, dbname = servers[0]
    dec_pwd = decrypt_password(password, aes_key)
    return f"postgresql://{username}:{dec_pwd}@{host}:{port}/{dbname}"

def main():
    try:
        db_url = get_render_url()
        print("Successfully extracted Render Production Database URL.")
    except Exception as e:
        print(f"Error getting connection string: {e}")
        return

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    
    # Standardize scheme
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    print(f"Connecting to database...")
    engine = create_engine(db_url, connect_args={"connect_timeout": 10})
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        from app.database.models.user import User
        from app.database.models.route import Route
        from app.database.models.bus import Bus, BusType
        from app.database.models.trip import Trip, TripStatus
        from app.database.models.booking import Booking, BookingStatus, PaymentStatus

        phone_number = "9392273983"
        user = db.query(User).filter_by(phone=phone_number).first()
        if not user:
            print(f"User with phone number {phone_number} not found in production database!")
            return

        print(f"Found Jayam, ID: {user.id}")

        # Ensure Route exists
        route = db.query(Route).filter_by(source_city="Delhi", destination_city="Chennai").first()
        if not route:
            route = Route(
                id=uuid.uuid4(),
                source_city="Delhi",
                destination_city="Chennai",
                distance_km=1746.0,
                estimated_duration_minutes=160,
            )
            db.add(route)
            db.commit()
            db.refresh(route)
            print(f"Created Route Delhi -> Chennai, ID: {route.id}")
        else:
            print(f"Route Delhi -> Chennai already exists, ID: {route.id}")

        # Ensure Bus exists
        bus_number = "6E-2134"
        bus = db.query(Bus).filter_by(bus_number=bus_number).first()
        if not bus:
            bus = Bus(
                id=uuid.uuid4(),
                bus_number=bus_number,
                bus_name="IndiGo Flight 6E-2134",
                registration_number="VT-IDG",
                bus_type=BusType.AC_SEATER,
                capacity=180,
            )
            db.add(bus)
            db.commit()
            db.refresh(bus)
            print(f"Created Flight (Bus) {bus_number}, ID: {bus.id}")
        else:
            print(f"Flight (Bus) {bus_number} already exists, ID: {bus.id}")

        # Ensure Trip exists (scheduled for 2026-08-15 10:30 UTC)
        departure_time = datetime(2026, 8, 15, 10, 30, tzinfo=timezone.utc)
        arrival_time = departure_time + timedelta(minutes=160)

        trip = db.query(Trip).filter_by(route_id=route.id, bus_id=bus.id, departure_time=departure_time).first()
        if not trip:
            trip = Trip(
                id=uuid.uuid4(),
                route_id=route.id,
                bus_id=bus.id,
                departure_time=departure_time,
                arrival_time=arrival_time,
                status=TripStatus.SCHEDULED,
                delay_minutes=0,
                available_seats=179,
            )
            db.add(trip)
            db.commit()
            db.refresh(trip)
            print(f"Created Trip for departure {departure_time}, ID: {trip.id}")
        else:
            print(f"Trip already exists, ID: {trip.id}")

        # Create Booking
        booking_code = "BK-939227"
        booking = db.query(Booking).filter_by(booking_code=booking_code).first()
        if not booking:
            booking = Booking(
                id=uuid.uuid4(),
                booking_code=booking_code,
                user_id=user.id,
                trip_id=trip.id,
                seat_number="12A",
                booking_status=BookingStatus.CONFIRMED,
                payment_status=PaymentStatus.PAID,
                booking_date=datetime.now(timezone.utc),
            )
            db.add(booking)
            db.commit()
            db.refresh(booking)
            print(f"Successfully seeded flight booking {booking_code} for Jayam!")
        else:
            print(f"Booking {booking_code} already exists.")

    except Exception as e:
        db.rollback()
        print(f"Database error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
