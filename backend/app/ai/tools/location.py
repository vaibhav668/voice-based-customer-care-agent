class LocationTool:

    def execute(
        self,
        booking_code,
    ):

        return self.service.get_bus_location(
            booking_code
        )