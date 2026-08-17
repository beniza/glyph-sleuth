// Enhancement only. Every fact on every page is in the served HTML; this makes
// a few of them adjustable. With JS off nothing here is missed except the
// ability to change a number.

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
