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
