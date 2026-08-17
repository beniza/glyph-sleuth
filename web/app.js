// Enhancement only. Every fact on every page is in the served HTML; this makes
// a few of them adjustable. With JS off nothing here is missed except the
// ability to change a number.

// --------------------------------------------------------------- the index
//
// Filter, facets and sort over rows the page already served. Nothing here
// fetches; with JS off the table is the full index, in name order.

const table = document.querySelector("table.index");
if (table) {
  const rows = [...table.tBodies[0].rows];
  const body = table.tBodies[0];
  const search = document.querySelector(".filter");
  const facets = [...document.querySelectorAll(".facet")];
  const sorts = [...document.querySelectorAll(".sort")];
  const showing = document.querySelector("[data-showing]");
  const empty = document.querySelector(".empty");

  let facet = "all";
  let sort = "name";

  const matches = (row, text) => {
    if (text && !row.dataset.name.includes(text)) return false;
    switch (facet) {
      case "all": return true;
      case "malayalam": return Number(row.dataset.malayalam) > 40;
      case "measured": return row.dataset.tier === "measured";
      case "not measured yet": return row.dataset.tier !== "measured";
      default: return row.dataset.verdict === facet;
    }
  };

  // Sorting a detached fragment, then putting it back once: reordering 1,885
  // rows in place is thousands of reflows and the page visibly stutters.
  const order = {
    name: (a, b) => a.dataset.name.localeCompare(b.dataset.name),
    coverage: (a, b) => Number(b.dataset.coverage) - Number(a.dataset.coverage),
    // Worst first — the reason to sort by verdict is to find what breaks.
    verdict: (a, b) => ["fail", "caveat", "clean", "none"].indexOf(a.dataset.verdict)
      - ["fail", "caveat", "clean", "none"].indexOf(b.dataset.verdict)
      || a.dataset.name.localeCompare(b.dataset.name),
  };

  const apply = () => {
    const text = (search?.value || "").trim().toLowerCase();
    const shown = rows.filter((row) => matches(row, text));
    shown.sort(order[sort]);

    const fragment = document.createDocumentFragment();
    shown.forEach((row) => fragment.appendChild(row));
    body.replaceChildren(fragment);   // clears what is there, then inserts once

    if (showing) showing.textContent = shown.length.toLocaleString();
    if (empty) empty.hidden = shown.length > 0;
    table.hidden = shown.length === 0;
  };

  search?.addEventListener("input", apply);
  facets.forEach((button) => button.addEventListener("click", () => {
    facet = button.dataset.facet;
    facets.forEach((other) => other.classList.toggle("on", other === button));
    apply();
  }));
  sorts.forEach((button) => button.addEventListener("click", () => {
    sort = button.dataset.sort;
    sorts.forEach((other) => other.classList.toggle("on", other === button));
    apply();
  }));
}

// ------------------------------------------------------------- the specimen
//
// The specimen size control. The size is in the URL so a size you chose is a
// size you can send someone — the same rule Compare follows for all its state.
const slider = document.querySelector(".size input");
const readout = document.querySelector(".size-value");
const specimens = document.querySelectorAll(".specimen");

if (slider && specimens.length) {
  const apply = (size, push) => {
    specimens.forEach((node) => { node.style.fontSize = `${size}px`; });
    if (readout) readout.textContent = `${size}px`;
    slider.value = size;
    if (push) {
      const url = new URL(location.href);
      url.searchParams.set("size", size);
      history.replaceState(null, "", url);   // replace, so Back still leaves the page
    }
  };

  const fromUrl = Number(new URL(location.href).searchParams.get("size"));
  if (fromUrl >= Number(slider.min) && fromUrl <= Number(slider.max)) apply(fromUrl, false);

  slider.addEventListener("input", () => apply(Number(slider.value), true));
}
