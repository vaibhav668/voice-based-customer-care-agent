import { getBooking } from "./api.js";
import { langManager } from "./language.js";
import { getToken } from "./storage.js";

const token = getToken();
if (!token) {
    location.href = "../index.html";
}

document.addEventListener("DOMContentLoaded", () => {
    langManager.init("lang-selector-container");
});

const container = document.getElementById("booking-card");

const bookingCode = new URLSearchParams(
    window.location.search
).get("code");

async function loadBooking() {

    try {

        const booking = await getBooking(bookingCode);

        container.innerHTML = `

<div class="booking-card">

<h2>${booking.bus_name}</h2>

<p><strong>Booking Code:</strong> ${booking.booking_code}</p>

<p><strong>Route:</strong> ${booking.source} → ${booking.destination}</p>

<p><strong>Seat Number:</strong> ${booking.seat_number}</p>

<p><strong>Booking Status:</strong> ${booking.booking_status}</p>

<p><strong>Payment Status:</strong> ${booking.payment_status}</p>

<p><strong>Departure:</strong> ${formatDate(booking.departure_time)}</p>

<p><strong>Arrival:</strong> ${formatDate(booking.arrival_time)}</p>

<br>

<button id="track-btn">

🚌 Track Bus

</button>

</div>

`;

        document
            .getElementById("track-btn")
            .onclick = () => {

                location.href =
                `trip.html?code=${booking.booking_code}`;

            };

    }

    catch (err) {

        container.innerHTML = `

<h2>Unable to load booking.</h2>

<p>${err.message}</p>

`;

    }

}

function formatDate(date) {

    return new Date(date).toLocaleString();

}

loadBooking();