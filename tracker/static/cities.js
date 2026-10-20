// City suggestions for the visit form and the trip form.
//
// The browser shows the <option>s of a <datalist> as suggestions while you
// type in a field that points to it with list="...". This script keeps those
// suggestions in step with the chosen state(s), using the /cities/<code> page,
// which returns a state's city names as JSON.

// Remember each state's list once it has been fetched.
const cityNamesByState = {};

// Fetch the city names of one state. "async" functions can wait for slow
// things like a download with "await", without freezing the page.
async function loadCityNames(code) {
  if (!cityNamesByState[code]) {
    const response = await fetch("/cities/" + code);
    cityNamesByState[code] = response.ok ? await response.json() : [];
  }
  return cityNamesByState[code];
}

// Replace a datalist's suggestions with these values.
function setSuggestions(datalist, values) {
  datalist.replaceChildren(...values.map(function (value) {
    const option = document.createElement("option");
    option.value = value;
    return option;
  }));
}

// --- Visit form: suggest the chosen state's cities. ---
const stateSelect = document.querySelector('select[name="state"]');
const visitCityList = document.getElementById("city-options");
if (stateSelect && visitCityList) {
  stateSelect.addEventListener("change", async function () {
    setSuggestions(visitCityList, await loadCityNames(stateSelect.value));
  });
}

// --- Trip form: suggest "City, ST" for every ticked state. ---
const tripCityList = document.getElementById("trip-city-options");
const stateBoxes = document.querySelectorAll('input[name="states"]');
if (tripCityList) {
  stateBoxes.forEach(function (box) {
    box.addEventListener("change", async function () {
      const ticked = [...stateBoxes].filter(b => b.checked).map(b => b.value);
      const values = [];
      for (const code of ticked) {
        for (const name of await loadCityNames(code)) {
          values.push(name + ", " + code);
        }
      }
      setSuggestions(tripCityList, values);
    });
  });
}

// --- Trip form: "Add another city" adds an empty row. ---
const addRowButton = document.querySelector(".add-city-row");
if (addRowButton) {
  addRowButton.addEventListener("click", function () {
    const rows = document.querySelector(".city-rows");
    // cloneNode() copies the last row, including its typed value; clear that.
    const newRow = rows.lastElementChild.cloneNode();
    newRow.removeAttribute("value");
    newRow.value = "";
    rows.appendChild(newRow);
    newRow.focus();
  });
}
