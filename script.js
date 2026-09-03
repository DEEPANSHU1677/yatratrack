/* =====================================================
   YATRATRACK
   SMART BUS TRACKING & TRAVEL ASSISTANCE
===================================================== */


/* =====================================================
   BUS DATA
===================================================== */

const buses = [
    {
        number: "PB-07-1234",
        type: "Ordinary Bus",
        from: "Jalandhar",
        to: "Pathankot",
        location: "Kartarpur",
        eta: 18,
        departure: "8:30 AM",
        distance: 6.8,
        nextStop: "Kartarpur",
        progress: 45,

        coordinates: [31.3800, 75.5800]
    },

    {
        number: "PB-08-5678",
        type: "Express Bus",
        from: "Jalandhar",
        to: "Pathankot",
        location: "Beas",
        eta: 35,
        departure: "8:45 AM",
        distance: 2.4,
        nextStop: "Kartarpur",
        progress: 65,

        coordinates: [31.5200, 75.2900]
    },

    {
        number: "PB-10-9012",
        type: "Ordinary Bus",
        from: "Jalandhar",
        to: "Pathankot",
        location: "Mukerian",
        eta: 52,
        departure: "9:15 AM",
        distance: 18.2,
        nextStop: "Mukerian",
        progress: 80,

        coordinates: [31.9500, 75.6200]
    }
];


/* =====================================================
   DOM ELEMENTS
===================================================== */

const fromInput = document.getElementById("fromInput");
const toInput = document.getElementById("toInput");

const swapBtn = document.getElementById("swapBtn");
const searchBtn = document.getElementById("searchBtn");

const busGrid = document.getElementById("busGrid");

const fromDisplay = document.getElementById("fromDisplay");
const toDisplay = document.getElementById("toDisplay");

const selectedBus = document.getElementById("selectedBus");
const etaElement = document.getElementById("eta");
const distanceElement = document.getElementById("distance");
const nextStopElement = document.getElementById("nextStop");

const progressFill = document.getElementById("progressFill");

const refreshLocation =
    document.getElementById("refreshLocation");

const viewAllBtn =
    document.getElementById("viewAllBtn");


/* =====================================================
   SELECTED BUS
===================================================== */

let currentBus = buses[1];

let map;
let busMarker;


/* =====================================================
   SWAP FROM / TO
===================================================== */

if (swapBtn) {

    swapBtn.addEventListener("click", function () {

        const temp = fromInput.value;

        fromInput.value = toInput.value;
        toInput.value = temp;

    });

}


/* =====================================================
   SEARCH BUSES
===================================================== */

if (searchBtn) {

    searchBtn.addEventListener("click", function () {

        const from =
            fromInput.value.trim();

        const to =
            toInput.value.trim();


        if (from === "" || to === "") {

            alert("Please enter both starting point and destination.");

            return;
        }


        fromDisplay.textContent = from;
        toDisplay.textContent = to;


        searchBuses(from, to);


        /* Scroll to bus results */

        document.getElementById("buses").scrollIntoView({
            behavior: "smooth"
        });

    });

}


/* =====================================================
   SEARCH FUNCTION
===================================================== */

function searchBuses(from, to) {

    const matchingBuses = buses.filter(function (bus) {

        return (
            bus.from.toLowerCase() === from.toLowerCase() &&
            bus.to.toLowerCase() === to.toLowerCase()
        );

    });


    if (matchingBuses.length === 0) {

        busGrid.innerHTML = `
            <div class="no-buses">
                <h3>No buses found</h3>
                <p>
                    Currently there are no buses available
                    for this route.
                </p>
            </div>
        `;

        return;
    }


    displayBuses(matchingBuses);

}


/* =====================================================
   DISPLAY BUS CARDS
===================================================== */

function displayBuses(busList) {

    busGrid.innerHTML = "";


    busList.forEach(function (bus, index) {

        const card = document.createElement("article");

        card.className =
            index === 1
                ? "bus-card featured"
                : "bus-card";


        card.innerHTML = `

            ${
                index === 1
                    ? `<div class="recommended">
                        RECOMMENDED
                       </div>`
                    : ""
            }


            <div class="bus-card-top">

                <div>

                    <div class="bus-number">
                        ${bus.number}
                    </div>

                    <span class="bus-type">
                        ${bus.type}
                    </span>

                </div>


                <span class="on-route">

                    <span>●</span>

                    On route

                </span>

            </div>


            <div class="route-name">

                ${bus.from}

                <span>→</span>

                ${bus.to}

            </div>


            <div class="bus-details">

                <div>

                    <small>
                        CURRENT LOCATION
                    </small>

                    <strong>
                        ${bus.location}
                    </strong>

                </div>


                <div>

                    <small>
                        ETA
                    </small>

                    <strong>
                        ${bus.eta} min
                    </strong>

                </div>


                <div>

                    <small>
                        DEPARTURE
                    </small>

                    <strong>
                        ${bus.departure}
                    </strong>

                </div>

            </div>


            <div class="stop-info">

                <div>

                    <i class="fa-solid fa-location-dot"></i>

                    <span>
                        Boarding: ${bus.from} Bus Stand
                    </span>

                </div>


                <div>

                    <i class="fa-solid fa-flag-checkered"></i>

                    <span>
                        Drop: ${bus.to}
                    </span>

                </div>

            </div>


            <button
                class="track-button"
                type="button"
                onclick="trackBus('${bus.number}')"
            >

                <i class="fa-solid fa-location-crosshairs"></i>

                Track bus

                <i class="fa-solid fa-arrow-right"></i>

            </button>

        `;


        busGrid.appendChild(card);

    });

}


/* =====================================================
   TRACK BUS
===================================================== */

function trackBus(busNumber) {

    const bus =
        buses.find(function (item) {

            return item.number === busNumber;

        });


    if (!bus) {
        return;
    }


    currentBus = bus;


    /* Update tracking information */

    selectedBus.textContent =
        bus.number;

    etaElement.textContent =
        `${bus.eta} min`;

    distanceElement.textContent =
        `${bus.distance} km`;

    nextStopElement.textContent =
        bus.nextStop;

    progressFill.style.width =
        `${bus.progress}%`;


    /* Update map */

    updateBusMarker(bus);


    /* Scroll to tracking */

    document
        .getElementById("tracking")
        .scrollIntoView({
            behavior: "smooth"
        });

}


/* =====================================================
   INITIALIZE MAP
===================================================== */

function initializeMap() {

    if (!document.getElementById("map")) {
        return;
    }


    /*
       Jalandhar / Punjab starting view
    */

    map = L.map("map").setView(
        [31.3260, 75.5762],
        9
    );


    /* OpenStreetMap */

    L.tileLayer(
        "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        {
            attribution:
                "&copy; OpenStreetMap contributors",

            maxZoom: 19
        }
    ).addTo(map);


    /* Create initial bus marker */

    updateBusMarker(currentBus);


    /* Add route stops */

    addRouteStops();

}


/* =====================================================
   BUS MARKER
===================================================== */

function updateBusMarker(bus) {

    if (!map) {
        return;
    }


    const busIcon = L.divIcon({

        className: "custom-bus-marker",

        html: `
            <div style="
                width:42px;
                height:42px;
                border-radius:50%;
                background:#1769e0;
                border:4px solid white;
                display:flex;
                align-items:center;
                justify-content:center;
                font-size:21px;
                box-shadow:0 5px 15px rgba(0,0,0,0.25);
            ">
                🚌
            </div>
        `,

        iconSize: [42, 42],

        iconAnchor: [21, 21]

    });


    if (busMarker) {

        busMarker.setLatLng(
            bus.coordinates
        );

        busMarker.setIcon(
            busIcon
        );

    } else {

        busMarker = L.marker(
            bus.coordinates,
            {
                icon: busIcon
            }
        ).addTo(map);

    }


    busMarker.bindPopup(`
        <strong>${bus.number}</strong><br>
        ${bus.location}<br>
        ETA: ${bus.eta} min
    `);


    map.setView(
        bus.coordinates,
        10
    );

}


/* =====================================================
   ROUTE STOPS
===================================================== */

function addRouteStops() {

    const stops = [

        {
            name: "Jalandhar",
            coordinates: [31.3260, 75.5762]
        },

        {
            name: "Kartarpur",
            coordinates: [31.4418, 75.4980]
        },

        {
            name: "Beas",
            coordinates: [31.5292, 75.2924]
        },

        {
            name: "Mukerian",
            coordinates: [31.9520, 75.6170]
        },

        {
            name: "Pathankot",
            coordinates: [32.2643, 75.6421]
        }

    ];


    const routeCoordinates =
        stops.map(function (stop) {

            return stop.coordinates;

        });


    /* Draw route */

    L.polyline(
        routeCoordinates,
        {
            color: "#1769e0",
            weight: 5,
            opacity: 0.75
        }
    ).addTo(map);


    /* Add stop markers */

    stops.forEach(function (stop) {

        L.circleMarker(
            stop.coordinates,
            {
                radius: 6,
                fillColor: "#ffffff",
                color: "#1769e0",
                weight: 3,
                fillOpacity: 1
            }
        )
        .addTo(map)
        .bindPopup(
            `<strong>${stop.name}</strong>`
        );

    });

}


/* =====================================================
   REFRESH LOCATION
===================================================== */

if (refreshLocation) {

    refreshLocation.addEventListener(
        "click",
        function () {

            if (!currentBus) {
                return;
            }


            /*
               Demo simulation:
               ETA decreases randomly.
            */

            if (currentBus.eta > 1) {

                currentBus.eta--;

            }


            /* Random small distance change */

            currentBus.distance =
                Math.max(
                    0.5,
                    currentBus.distance - 0.1
                );


            /* Update UI */

            etaElement.textContent =
                `${currentBus.eta} min`;

            distanceElement.textContent =
                `${currentBus.distance.toFixed(1)} km`;


            /* Update popup */

            updateBusMarker(currentBus);


            /* Button animation */

            refreshLocation.style.transform =
                "rotate(360deg)";


            setTimeout(function () {

                refreshLocation.style.transform =
                    "rotate(0deg)";

            }, 500);

        }
    );

}


/* =====================================================
   VIEW ALL
===================================================== */

if (viewAllBtn) {

    viewAllBtn.addEventListener(
        "click",
        function () {

            displayBuses(buses);

        }
    );

}


/* =====================================================
   MOBILE MENU
===================================================== */

const menuBtn =
    document.getElementById("menuBtn");


if (menuBtn) {

    menuBtn.addEventListener(
        "click",
        function () {

            const nav =
                document.querySelector(".nav-links");


            if (nav) {

                nav.classList.toggle(
                    "mobile-active"
                );

            }

        }
    );

}


/* =====================================================
   START APPLICATION
===================================================== */

document.addEventListener(
    "DOMContentLoaded",
    function () {

        initializeMap();

    }
);