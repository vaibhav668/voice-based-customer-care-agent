import { getBookings } from "./api.js";
import { langManager } from "./language.js";
import { getToken } from "./storage.js";

const token = getToken();
if (!token) {
    location.href = "../index.html";
}

document.addEventListener("DOMContentLoaded", () => {
    langManager.init("lang-selector-container");
});

const container = document.getElementById("booking-list");

async function loadBookings() {

    try {

        const response = await getBookings();

        // API returns { success, message, data: [...] } — unwrap the data array
        const bookings = response.data || response;

        container.innerHTML = "";

        if (!Array.isArray(bookings) || bookings.length === 0) {

            container.innerHTML = "<h2>No bookings found.</h2>";

            return;

        }

        bookings.forEach(booking => {

            container.insertAdjacentHTML(

                "beforeend",

                `
<div class="booking-card">

<h2>${booking.bus_name}</h2>

<p><strong>Booking:</strong> ${booking.booking_code}</p>

<p><strong>Route:</strong> ${booking.source} → ${booking.destination}</p>

<p><strong>Seat:</strong> ${booking.seat_number}</p>

<p><strong>Status:</strong> ${booking.booking_status}</p>

<p><strong>Payment:</strong> ${booking.payment_status}</p>

<button
onclick="location.href='booking.html?code=${booking.booking_code}'">

View Details

</button>

</div>
`

            );

        });

    }

    catch (err) {

        container.innerHTML = `

<h2>Unable to load bookings</h2>

<p>${err.message}</p>

`;

    }

}

loadBookings();