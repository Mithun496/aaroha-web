/* ================= CATEGORY FILTER ================= */

function filterCategory(category, button) {

    const cards = document.querySelectorAll(".destination-card");

    document.querySelectorAll(".category").forEach(item => {
        item.classList.remove("active");
    });

    button.classList.add("active");

    cards.forEach(card => {

        if (category === "all") {
            card.style.display = "block";
            return;
        }

        const categories =
            card.dataset.category.split(" ");

        if (categories.includes(category)) {
            card.style.display = "block";
        } else {
            card.style.display = "none";
        }

    });

}


/* ================= SEARCH ================= */

function searchPlaces() {

    const input =
        document.getElementById("searchInput");

    const query =
        input.value.trim().toLowerCase();

    const cards =
        document.querySelectorAll(".destination-card");

    if (!query) {

        cards.forEach(card => {
            card.style.display = "block";
        });

        return;
    }

    cards.forEach(card => {

        const text =
            card.innerText.toLowerCase();

        if (text.includes(query)) {
            card.style.display = "block";
        } else {
            card.style.display = "none";
        }

    });

}


/* ENTER KEY SEARCH */

document
    .getElementById("searchInput")
    ?.addEventListener("keydown", function(event) {

        if (event.key === "Enter") {
            searchPlaces();
        }

    });


/* ================= SAVE DESTINATION ================= */

function toggleSave(button) {

    button.classList.toggle("saved");

    if (button.classList.contains("saved")) {

        button.innerHTML = "♥";

        button.setAttribute(
            "aria-label",
            "Remove from saved places"
        );

    } else {

        button.innerHTML = "♡";

        button.setAttribute(
            "aria-label",
            "Save destination"
        );

    }

}


/* ================= VIEW ALL ================= */

function showAllDestinations() {

    const cards =
        document.querySelectorAll(".destination-card");

    cards.forEach(card => {
        card.style.display = "block";
    });

    document.querySelectorAll(".category")
        .forEach(button => {
            button.classList.remove("active");
        });

    document
        .querySelector(".category")
        ?.classList.add("active");

}


/* ================= IMAGE FALLBACK ================= */

document.querySelectorAll("img").forEach(img => {

    img.addEventListener("error", function() {

        /*
         * If an external image fails,
         * keep the card visually usable.
         */

        this.style.display = "none";

        this.parentElement.style.background =
            "linear-gradient(135deg, #073a34, #011b18)";

    });

});