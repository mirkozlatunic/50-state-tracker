// Dot details on phones and tablets.
//
// With a mouse, hovering a city dot shows its tooltip and clicking opens its
// state. Touch screens can't hover, so there the first tap on a dot shows its
// details in the box under the map, and a second tap on the same dot opens
// its state.

const detailsBox = document.getElementById("dot-details");
let selectedLink = null;

document.querySelectorAll(".dot-link").forEach(function (link) {
  link.addEventListener("click", function (event) {
    // Asked at tap time: "(hover: none)" means the screen can't hover.
    const touchScreen = window.matchMedia("(hover: none)").matches;
    if (!touchScreen || link === selectedLink) {
      return; // let the link open the state page
    }

    // First tap: show the details instead of opening the state.
    event.preventDefault();
    if (selectedLink) {
      selectedLink.classList.remove("selected");
    }
    selectedLink = link;
    link.classList.add("selected");

    // textContent (not innerHTML) shows the text as text, never as HTML.
    const text = document.createElement("p");
    text.textContent = link.dataset.details;
    const open = document.createElement("a");
    open.href = link.getAttribute("href");
    open.textContent = "Open " + link.dataset.stateName + " →";
    detailsBox.replaceChildren(text, open);
    detailsBox.hidden = false;
  });
});
