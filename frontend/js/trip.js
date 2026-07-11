import { getTrip } from "./api.js";
import { langManager } from "./language.js";
import { getToken } from "./storage.js";

const token = getToken();
if (!token) {
    location.href = "../index.html";
}

document.addEventListener("DOMContentLoaded", () => {
    langManager.init("lang-selector-container");
});

const container =
document.getElementById("trip-card");

const bookingCode =
new URLSearchParams(
window.location.search
).get("code");

async function loadTrip(){

    try{

        const trip =
        await getTrip(bookingCode);

        container.innerHTML = `

<div class="booking-card">

<h2>${trip.bus_name}</h2>

<p>

<strong>Booking Code:</strong>

${trip.booking_code}

</p>

<p>

<strong>Route:</strong>

${trip.source}

→

${trip.destination}

</p>

<p>

<strong>Status:</strong>

${statusBadge(trip.trip_status)}

</p>

<p>

<strong>Delay:</strong>

${trip.delay_minutes} Minutes

</p>

<p>

<strong>Departure:</strong>

${formatDate(trip.departure_time)}

</p>

<p>

<strong>Arrival:</strong>

${formatDate(trip.arrival_time)}

</p>

</div>

`;

    }

    catch(err){

        container.innerHTML=`

<h2>

Unable to load trip.

</h2>

<p>

${err.message}

</p>

`;

    }

}

function formatDate(date){

    return new Date(date).toLocaleString();

}

function statusBadge(status){

    switch(status){

        case "RUNNING":

            return "🟢 RUNNING";

        case "DELAYED":

            return "🟠 DELAYED";

        case "ARRIVED":

            return "✅ ARRIVED";

        case "CANCELLED":

            return "🔴 CANCELLED";

        default:

            return status;

    }

}

loadTrip();