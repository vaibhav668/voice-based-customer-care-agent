-- ====================================================================
-- SEED BOOKINGS SQL FOR JAYAM (9392273983)
-- JOURNEY 1: FLIGHT (DELHI TO CHENNAI)
-- JOURNEY 2: BUS (DELHI TO JAIPUR)
-- DATABASE: PostgreSQL Production (supportai_9q4b)
-- ====================================================================

DO $$
DECLARE
    v_user_id UUID;
    v_rf_id UUID; -- Route Flight
    v_bf_id UUID; -- Bus Flight
    v_tf_id UUID; -- Trip Flight
    
    v_rb_id UUID; -- Route Bus
    v_bb_id UUID; -- Bus Bus
    v_tb_id UUID; -- Trip Bus
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

    -- ----------------------------------------------------
    -- SEED FLIGHT BOOKING (BK-939227)
    -- ----------------------------------------------------
    
    -- Ensure flight route exists
    INSERT INTO public.routes (id, source_city, destination_city, distance_km, estimated_duration_minutes, created_at, updated_at)
    VALUES (gen_random_uuid(), 'Delhi', 'Chennai', 1746.0, 160, NOW(), NOW())
    ON CONFLICT DO NOTHING;

    SELECT id INTO v_rf_id 
    FROM public.routes 
    WHERE source_city = 'Delhi' AND destination_city = 'Chennai' 
    LIMIT 1;

    -- Ensure flight (bus record) exists
    INSERT INTO public.buses (id, bus_number, bus_name, registration_number, bus_type, capacity, created_at, updated_at)
    VALUES (gen_random_uuid(), '6E-2134', 'IndiGo Flight 6E-2134', 'VT-IDG', 'AC_SEATER'::bustype, 180, NOW(), NOW())
    ON CONFLICT (bus_number) DO UPDATE SET bus_name = EXCLUDED.bus_name;

    SELECT id INTO v_bf_id 
    FROM public.buses 
    WHERE bus_number = '6E-2134' 
    LIMIT 1;

    -- Ensure trip exists
    INSERT INTO public.trips (id, route_id, bus_id, departure_time, arrival_time, status, delay_minutes, available_seats, created_at, updated_at)
    VALUES (gen_random_uuid(), v_rf_id, v_bf_id, '2026-08-15 10:30:00+00'::TIMESTAMPTZ, '2026-08-15 13:10:00+00'::TIMESTAMPTZ, 'SCHEDULED'::tripstatus, 0, 179, NOW(), NOW())
    ON CONFLICT DO NOTHING;

    SELECT id INTO v_tf_id 
    FROM public.trips 
    WHERE route_id = v_rf_id AND bus_id = v_bf_id AND departure_time = '2026-08-15 10:30:00+00'::TIMESTAMPTZ
    LIMIT 1;

    -- Create Booking
    INSERT INTO public.bookings (id, booking_code, user_id, trip_id, seat_number, booking_status, payment_status, booking_date, created_at, updated_at)
    VALUES (gen_random_uuid(), 'BK-939227', v_user_id, v_tf_id, '12A', 'CONFIRMED'::bookingstatus, 'PAID'::paymentstatus, NOW(), NOW(), NOW())
    ON CONFLICT (booking_code) DO UPDATE 
    SET user_id = EXCLUDED.user_id, trip_id = EXCLUDED.trip_id, booking_status = EXCLUDED.booking_status, payment_status = EXCLUDED.payment_status;

    -- ----------------------------------------------------
    -- SEED BUS BOOKING (BK-939228)
    -- ----------------------------------------------------
    
    -- Ensure bus route exists
    INSERT INTO public.routes (id, source_city, destination_city, distance_km, estimated_duration_minutes, created_at, updated_at)
    VALUES (gen_random_uuid(), 'Delhi', 'Jaipur', 280.0, 315, NOW(), NOW())
    ON CONFLICT DO NOTHING;

    SELECT id INTO v_rb_id 
    FROM public.routes 
    WHERE source_city = 'Delhi' AND destination_city = 'Jaipur' 
    LIMIT 1;

    -- Ensure bus exists
    INSERT INTO public.buses (id, bus_number, bus_name, registration_number, bus_type, capacity, created_at, updated_at)
    VALUES (gen_random_uuid(), 'AP39AB1001', 'Volvo Multi Axle AC Sleeper', 'AP39BUS1001', 'AC_SLEEPER'::bustype, 36, NOW(), NOW())
    ON CONFLICT (bus_number) DO UPDATE SET bus_name = EXCLUDED.bus_name;

    SELECT id INTO v_bb_id 
    FROM public.buses 
    WHERE bus_number = 'AP39AB1001' 
    LIMIT 1;

    -- Ensure trip exists
    INSERT INTO public.trips (id, route_id, bus_id, departure_time, arrival_time, status, delay_minutes, available_seats, created_at, updated_at)
    VALUES (gen_random_uuid(), v_rb_id, v_bb_id, '2026-08-16 22:00:00+00'::TIMESTAMPTZ, '2026-08-17 03:15:00+00'::TIMESTAMPTZ, 'SCHEDULED'::tripstatus, 0, 35, NOW(), NOW())
    ON CONFLICT DO NOTHING;

    SELECT id INTO v_tb_id 
    FROM public.trips 
    WHERE route_id = v_rb_id AND bus_id = v_bb_id AND departure_time = '2026-08-16 22:00:00+00'::TIMESTAMPTZ
    LIMIT 1;

    -- Create Booking
    INSERT INTO public.bookings (id, booking_code, user_id, trip_id, seat_number, booking_status, payment_status, booking_date, created_at, updated_at)
    VALUES (gen_random_uuid(), 'BK-939228', v_user_id, v_tb_id, '15', 'CONFIRMED'::bookingstatus, 'PAID'::paymentstatus, NOW(), NOW(), NOW())
    ON CONFLICT (booking_code) DO UPDATE 
    SET user_id = EXCLUDED.user_id, trip_id = EXCLUDED.trip_id, booking_status = EXCLUDED.booking_status, payment_status = EXCLUDED.payment_status;

    RAISE NOTICE 'Successfully seeded all bookings for Jayam!';
END $$;
