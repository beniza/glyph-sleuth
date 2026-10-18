// A "copy link" button on every section heading that has an id.
//
// The ids are in the served markup, so a link to a section works with no
// script at all. What needs script is copying it: the button copies the full
// address of this page as it is now — Inspect's text, an index filter, Try it's
// line — plus the section, and puts that address in the bar too. Called again
// by any page that draws headings after load, which is why it skips a heading
// that already has one.
export function sectionLinks(root = document) {
  for (const heading of root.querySelectorAll("h2.eyebrow[id]")) {
    if (heading.querySelector(".section-link")) continue;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "section-link";
    button.textContent = "copy link";
    button.setAttribute("aria-label", `Copy a link to “${heading.textContent.trim()}”`);
    button.addEventListener("click", async () => {
      const url = new URL(location.href);
      url.hash = heading.id;
      history.replaceState(null, "", url);   // replace, so Back still leaves the page
      try {
        await navigator.clipboard.writeText(url.href);
        button.textContent = "copied";
      } catch {
        // The address bar now holds the link even where the clipboard is refused.
        button.textContent = "link in address bar";
      }
      setTimeout(() => { button.textContent = "copy link"; }, 1400);
    });
    heading.append(button);
  }
}

// Every `.copy` button on the site, wherever it is.
//
// This lived inside inspect.js, bound to one panel, so a copy button on any
// other page did nothing at all. One delegated listener on the document handles
// them all: a button carries what it copies in `data-copy`, and nothing else
// needs to know it exists.
//
// The button says what happened. Writing to the clipboard is silent, and a
// button that gives no sign is a button people press twice.
export function copyButtons(root = document) {
  root.addEventListener("click", async (event) => {
    const button = event.target.closest(".copy");
    if (!button) return;
    const was = button.textContent;
    try {
      await navigator.clipboard.writeText(button.dataset.copy);
      button.textContent = "copied";
    } catch {
      // Denied permission, or an insecure origin. Saying so beats a button that
      // claims success and left the clipboard alone.
      button.textContent = "press ⌘C";
      const range = document.createRange();
      const source = button.closest(".snippet-wrap")?.querySelector(".snippet");
      if (source) {
        range.selectNodeContents(source);
        getSelection().removeAllRanges();
        getSelection().addRange(range);
      }
    }
    setTimeout(() => { button.textContent = was; }, 1200);
  });
}
