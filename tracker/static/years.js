// Drag and drop for the year page.
//
// This is JavaScript: it runs in the browser, not in Flask. Dropping a trip
// card on another year does the same as the card's "Move to" menu: it picks
// that year in the menu and submits the form. Flask then checks the rules and
// shows the year page again, so all the numbers on it are fresh.

// When you pick a card up, remember which trip it is.
document.querySelectorAll(".trip-card").forEach(function (card) {
  card.addEventListener("dragstart", function (event) {
    event.dataTransfer.setData("text/plain", card.dataset.tripId);
    card.classList.add("dragging");
  });
  card.addEventListener("dragend", function () {
    card.classList.remove("dragging");
  });
});

document.querySelectorAll(".year").forEach(function (column) {
  // preventDefault() on "dragover" tells the browser this column accepts drops.
  column.addEventListener("dragover", function (event) {
    event.preventDefault();
    column.classList.add("drop-target");
  });

  // Only remove the highlight when the mouse really leaves the column,
  // not when it moves onto a card inside it.
  column.addEventListener("dragleave", function (event) {
    if (!column.contains(event.relatedTarget)) {
      column.classList.remove("drop-target");
    }
  });

  column.addEventListener("drop", function (event) {
    event.preventDefault();
    column.classList.remove("drop-target");

    const tripId = event.dataTransfer.getData("text/plain");
    const card = document.querySelector('.trip-card[data-trip-id="' + tripId + '"]');
    // Dropped back on its own year (or something that isn't a trip card): nothing to do.
    if (!card || card.closest(".year") === column) {
      return;
    }

    const form = card.querySelector(".move-form");
    form.elements.year.value = column.dataset.year;
    form.submit();
  });
});
