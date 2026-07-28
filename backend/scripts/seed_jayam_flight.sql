-- ====================================================================
-- SEED BOOKINGS SQL FOR JAYAM (9392273983)
-- JOURNEY TYPE: FLIGHT (DELHI TO CHENNAI)
-- DATABASE: PostgreSQL Production (supportai_9q4b)
-- ====================================================================

DO $$
DECLARE
    v_user_id UUID;
    v_route_id UUID;
    v_bus_id UUID;
    v_trip_id UUID;
    v_booking_id UUID;
BEGIN
    -- 1. Locate the existing registered user by phone number
    SELECT id INTO v_user_id 
    FROM public.users 
    WHERE phone = '9392273983' 
    LIMIT 1;

    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'User Jayam with phone 9392273983 not found in database. Please register the user first.';
    END IF;

    RAISE NOTICE 'Found User Jayam, ID: %', v_user_id;

    -- 2. Ensure the Delhi to Chennai flight route exists
    INSERT INTO public.routes (id, source_city, destination_city, distance_km, estimated_duration_minutes, created_at, updated_at)
    VALUES (gen_random_uuid(), 'Delhi', 'Chennai', 1746.0, 160, NOW(), NOW())
    ON CONFLICT DO NOTHING;

    SELECT id INTO v_route_id 
    FROM public.routes 
    WHERE source_city = 'Delhi' AND destination_city = 'Chennai' 
    LIMIT 1;

    -- 3. Ensure the Flight (represented as a Bus record) exists
    INSERT INTO public.buses (id, bus_number, bus_name, registration_number, bus_type, capacity, created_at, updated_at)
    VALUES (gen_random_uuid(), '6E-2134', 'IndiGo Flight 6E-2134', 'VT-IDG', 'AC_SEATER'::bustype, 180, NOW(), NOW())
    ON CONFLICT (bus_number) DO UPDATE SET bus_name = EXCLUDED.bus_name;

    SELECT id INTO v_bus_id 
    FROM public.buses 
    WHERE bus_number = '6E-2134' 
    LIMIT 1;

    -- 4. Ensure the Trip (Flight Schedule) exists for 2026-08-15 10:30 UTC
    INSERT INTO public.trips (id, route_id, bus_id, departure_time, arrival_time, status, delay_minutes, available_seats, created_at, updated_at)
    VALUES (gen_random_uuid(), v_route_id, v_bus_id, '2026-08-15 10:30:00+00'::TIMESTAMPTZ, '2026-08-15 13:10:00+00'::TIMESTAMPTZ, 'SCHEDULED'::tripstatus, 0, 179, NOW(), NOW())
    ON CONFLICT DO NOTHING;

    SELECT id INTO v_trip_id 
    FROM public.trips 
    WHERE route_id = v_route_id AND bus_id = v_bus_id AND departure_time = '2026-08-15 10:30:00+00'::TIMESTAMPTZ
    LIMIT 1;

    -- 5. Insert the Confirmed Booking (BK-939227)
    INSERT INTO public.bookings (id, booking_code, user_id, trip_id, seat_number, booking_status, payment_status, booking_date, created_at, updated_at)
    VALUES (gen_random_uuid(), 'BK-939227', v_user_id, v_trip_id, '12A', 'CONFIRMED'::bookingstatus, 'PAID'::paymentstatus, NOW(), NOW(), NOW())
    ON CONFLICT (booking_code) DO UPDATE 
    SET user_id = EXCLUDED.user_id, trip_id = EXCLUDED.trip_id, booking_status = EXCLUDED.booking_status, payment_status = EXCLUDED.payment_status;

    RAISE NOTICE 'Successfully seeded flight booking BK-939227 for Jayam!';
END $$;
