class BookingTool:

    def execute(
        self,
        booking_code: str,
    ):

        booking = booking_service.get_booking_details(
            booking_code
        )

        return booking