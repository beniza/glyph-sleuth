// What only a browser can answer: `npx playwright test`, after a build.
//
// Every bug in this project that reached a deploy was of one kind — a page that
// passed 99 unit tests and was wrong when someone looked at it. A nav item that
// 404s. A long word painting over its neighbour. A face reported as not drawing
// a character it was drawing. None of those are visible from Python or Node.
//
// So these tests are deliberately not a screenshot suite. They assert the things
// that went wrong: links resolve, nothing overflows, the fallback marking tells
// the truth, and the pages still work with JavaScript switched off.
import { test, expect } from "@playwright/test";

const BASE = "/glyph-sleuth";

// A page whose own content overflows sideways is broken, whatever it looks like.
async function expectNoSidewaysScroll(page) {
  const overflow = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    client: document.documentElement.clientWidth,
  }));
  expect(overflow.scroll, "the page scrolls sideways").toBeLessThanOrEqual(
    overflow.client + 1);
}

test.describe("the nav", () => {
  test("every link in it resolves", async ({ page, baseURL }) => {
    await page.goto(`${BASE}/`);
    const hrefs = await page.locator("nav a").evaluateAll(
      (nodes) => nodes.map((node) => node.getAttribute("href")));
    expect(hrefs.length).toBeGreaterThan(3);
    for (const href of hrefs) {
      const response = await page.request.get(new URL(href, baseURL).toString());
      expect(response.status(), `${href} is in the nav and does not resolve`).toBe(200);
    }
  });

  test("Tools opens by click and by keyboard", async ({ page }) => {
    await page.goto(`${BASE}/`);
    const tools = page.locator("details.tools");
    await expect(tools).toHaveJSProperty("open", false);
    await tools.locator("summary").click();
    await expect(tools).toHaveJSProperty("open", true);
    await expect(page.locator(".tools-menu a", { hasText: "Inspect" })).toBeVisible();

    // A disclosure a keyboard cannot open is a menu that does not exist for
    // anyone using one.
    await page.keyboard.press("Escape");
    await page.reload();
    await page.locator("details.tools summary").press("Enter");
    await expect(page.locator("details.tools")).toHaveJSProperty("open", true);
  });
});

test.describe("Inspect", () => {
  test("reads a sequence and names it", async ({ page }) => {
    await page.goto(`${BASE}/inspect/?t=%E0%B4%A8%E0%B5%8D%E0%B4%B1`);   // ന്റ, legacy nta
    await expect(page.locator("#inspect-reading")).toContainText("Read as");
    const out = page.locator("#inspect-out");
    await expect(out).toContainText("MALAYALAM LETTER NA");
    // The authored sequence list is what lets it say which sequence this is.
    await expect(out).toContainText("ntaLegacy");
    // And the cluster count, which is the point of the page.
    await expect(out).toContainText("codepoints");
  });

  test("a long word does not overflow the family panel", async ({ page }) => {
    // The bug: eight tiles of one long Malayalam word painted across each other.
    await page.goto(`${BASE}/inspect/?t=%E0%B4%85%E0%B4%B5%E0%B4%A8%E0%B5%8D%E0%B4%B1%E0%B5%86%20%E0%B4%85%E0%B4%B5%E0%B4%A8%E0%B5%86%E0%B4%B1`);
    await page.locator(".draws").first().waitFor();
    await expectNoSidewaysScroll(page);

    // No drawing may spill outside the box that is supposed to contain it.
    const spills = await page.locator(".draws").evaluateAll((nodes) => nodes
      .filter((node) => {
        const glyph = node.querySelector(".tile-glyph");
        if (!glyph) return false;
        return glyph.getBoundingClientRect().right > node.getBoundingClientRect().right + 1;
      }).length);
    expect(spills, "a drawing spills out of its own box").toBe(0);
  });

  test("copy hands over what it shows", async ({ page, context }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    await page.goto(`${BASE}/inspect/?t=%E0%B4%95`);
    await page.locator(".pairs .copy").first().click();
    const copied = await page.evaluate(() => navigator.clipboard.readText());
    // The codepoints row is first, so what lands on the clipboard is that.
    expect(copied).toContain("U+0D15");
  });
});

test.describe("the Use it snippet", () => {
  // The snippet is the one thing a reader takes away from a family page, and
  // until now the only copy button on the site was Inspect's, bound to Inspect's
  // own panel. This asserts two things that were both wrong on the way here:
  // that the button exists off /inspect/ at all, and that what it puts on the
  // clipboard is the snippet rather than its HTML escaping — a stylesheet URL
  // arriving as "&amp;display=swap" 404s when you paste it.
  test("copies the snippet itself, entities and all", async ({ page, context }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    await page.goto(`${BASE}/font/anjalioldlipi/`);

    const shown = (await page.locator(".snippet").first().innerText()).trim();
    await page.locator(".snippet-wrap .copy").first().click();
    const copied = await page.evaluate(() => navigator.clipboard.readText());

    // Line endings are the platform clipboard's business: Windows hands back
    // CRLF for the LF we wrote, which is what a paste into Notepad should be.
    expect(copied.replace(/\r\n/g, "\n").trim()).toBe(shown);
    expect(copied).toContain("<link rel=\"stylesheet\"");
    expect(copied, "the clipboard got HTML entities").not.toContain("&amp;");
    expect(copied, "the clipboard got HTML entities").not.toContain("&lt;");
  });

  test("a Google family's snippet pastes as a working URL", async ({ page, context }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    await page.goto(`${BASE}/font/abeezee/`);
    await page.locator(".snippet-wrap .copy").first().click();
    const copied = await page.evaluate(() => navigator.clipboard.readText());
    expect(copied).toContain("?family=ABeeZee&display=swap");
  });
});

test.describe("Try it", () => {
  const type = async (page, text) => {
    await page.goto(`${BASE}/font/rit-rachana/`);
    await page.evaluate(() => document.fonts.ready);
    await page.fill('[data-try="text"]', text);
    await page.click('[data-try="go"]');
    await expect(page.locator(".try-out")).toBeVisible();
  };

  test("sets what you typed in this family, and marks what it cannot draw", async ({ page }) => {
    // Malayalam this font has, Kannada it does not. Both in one line, because
    // the panel's whole job is telling them apart inside a run of text.
    await type(page, "മലയാളം ಕನ್ನಡ");

    const face = await page.locator(".try-out").evaluate(
      (node) => getComputedStyle(node).fontFamily);
    expect(face).toContain("RIT Rachana");

    const marked = await page.locator(".try-out .uncovered").evaluateAll(
      (nodes) => nodes.map((node) => node.textContent));
    expect(marked.join(""), "Kannada is not in this Malayalam face").toContain("ಕ");
    expect(marked.join(""), "Malayalam it has was marked as missing").not.toContain("മ");
    await expect(page.locator('[data-try="note"]')).toContainText("not in RIT Rachana");
  });

  test("reads codepoints and a range, the way Inspect does", async ({ page }) => {
    await type(page, "U+0D15 U+0D4D U+0D15");
    await expect(page.locator(".try-out")).toHaveText("ക്ക");

    // A range is a chart. The cap matters: 0000..10FFFF must not try to paint
    // a million characters into a panel.
    await page.fill('[data-try="text"]', "0000..10FFFF");
    await page.click('[data-try="go"]');
    const painted = await page.locator(".try-out").evaluate((node) => [...node.textContent].length);
    expect(painted).toBeLessThanOrEqual(256);
  });

  test("the size slider moves the preview and nothing else", async ({ page }) => {
    await type(page, "മലയാളം");
    const before = await page.locator(".try-out").evaluate((n) => getComputedStyle(n).fontSize);
    await page.locator('[data-try="size"]').fill("48");
    const after = await page.locator(".try-out").evaluate((n) => getComputedStyle(n).fontSize);
    expect(before).toBe("14px");
    expect(after).toBe("48px");
    // The family's own specimen at the top of the page has its own control.
    const specimen = await page.locator(".specimen").first()
      .evaluate((n) => getComputedStyle(n).fontSize);
    expect(specimen).not.toBe("48px");
  });

  test("turning a feature off changes what is drawn", async ({ page }) => {
    // akhn builds the Malayalam conjuncts. With it off the same codepoints draw
    // as separate letters, which is the difference the panel exists to show.
    // Measured across the text, not the box: the panel is a block and its own
    // width never moves, which is how this test first passed while proving
    // nothing.
    const drawnWidth = () => page.locator(".try-out").evaluate((node) => {
      const range = document.createRange();
      range.selectNodeContents(node);
      return range.getBoundingClientRect().width;
    });

    await type(page, "ക്ക");
    const on = await drawnWidth();
    // The features are folded away by default — nine to thirty tags is a wall,
    // and the default state is the one the reader wants first.
    await page.locator(".try-features summary").click();
    await page.locator('[data-feature="akhn"]').uncheck();
    await expect(page.locator(".try-out")).toBeVisible();
    const off = await drawnWidth();
    // The conjunct is one glyph; two letters side by side are wider. If Chrome
    // ever stops honouring font-feature-settings for a mandatory Indic feature,
    // this fails and the control has to go rather than sit there doing nothing.
    expect(off, "unticking akhn drew the same thing").toBeGreaterThan(on);
  });
});

test.describe("a face that is drawing is not marked as absent", () => {
  test("families on a character page render it", async ({ page }) => {
    // The bug this exists for: Dyuthi was marked as not drawing ക, which it
    // draws perfectly well. A false positive here is worse than no check at all,
    // because it tells a reader a working font is broken.
    await page.goto(`${BASE}/char/0D15/`);
    const tiles = page.locator(".drawn .draws");
    await expect(tiles.first()).toBeVisible();

    // Give the webfonts a chance to arrive, then let the check run.
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(1500);

    const marked = await page.locator(".tile-glyph.fallback").evaluateAll(
      (nodes) => nodes.map((node) => node.dataset.face));
    const names = await page.locator(".draws-name").evaluateAll(
      (nodes) => nodes.map((node) => node.textContent.trim()));
    expect(marked, `marked as not drawing: ${marked.join(", ")} of ${names.length}`)
      .toEqual([]);
  });

  test("but a family whose stylesheet never arrived is marked", async ({ page }) => {
    // The check has to be capable of saying no, or it is decoration — and the
    // browser's own check() cannot: Chrome answers true for a family that does
    // not exist. What is provable is whether our @font-face arrived, so that is
    // what is asserted here.
    await page.goto(`${BASE}/char/0D15/`);
    await page.evaluate(() => document.fonts.ready);

    const verdicts = await page.evaluate(async () => {
      const unquote = (name) => name.replace(/^["']|["']$/g, "");
      const has = (family) => [...document.fonts]
        .some((face) => unquote(face.family) === family);
      return { real: has("Dyuthi"), invented: has("No Such Family At All") };
    });
    expect(verdicts.real, "a family the page draws has no @font-face").toBe(true);
    expect(verdicts.invented, "a family that does not exist has an @font-face").toBe(false);
  });
});

test.describe("with JavaScript off", () => {
  test.use({ javaScriptEnabled: false });

  test("the index is still the whole index", async ({ page }) => {
    // The reason the pages are generated rather than assembled in the browser.
    await page.goto(`${BASE}/fonts/`);
    const rows = await page.locator("table.index tbody tr").count();
    // Compared with the number the page itself states, so this holds for a
    // --limit build as well as the full one: every family it claims to index is
    // a row in the served HTML, with no script involved.
    const claimed = Number((await page.locator(".showing").textContent())
      .replace(/.*of\s*/, "").replace(/[^0-9]/g, ""));
    expect(rows).toBe(claimed);
    expect(rows).toBeGreaterThan(10);
    await expect(page.locator("h1")).toHaveText("Font families");
  });

  test("a font page still carries its evidence", async ({ page }) => {
    await page.goto(`${BASE}/font/manjari/`);
    await expect(page.locator("h1")).toContainText("Manjari");
    await expect(page.locator("body")).toContainText("Coverage, by block");
  });

  test("Inspect says it needs JavaScript rather than showing nothing", async ({ page }) => {
    await page.goto(`${BASE}/inspect/`);
    // Read as markup, not text: with scripting disabled the parser keeps noscript
    // content as raw text, so textContent is empty even though the words are there.
    expect(await page.locator("noscript").innerHTML()).toContain("JavaScript");
  });
});

test.describe("at 380px, which the brief requires", () => {
  test.use({ viewport: { width: 380, height: 800 } });

  for (const path of ["/", "/fonts/", "/font/manjari/", "/char/0D15/", "/inspect/?t=%E0%B4%95"]) {
    test(`${path} does not scroll sideways`, async ({ page }) => {
      await page.goto(`${BASE}${path}`);
      await page.waitForTimeout(400);
      await expectNoSidewaysScroll(page);
    });
  }
});

test.describe("a page that draws a family has that family", () => {
  // The /char/ grid learned this lesson and nothing else did. A family page
  // sets its specimen and every row of the evidence matrix in the family's own
  // name; a glyphs page sets nine hundred cells in it. Where the family has no
  // webfont those are drawn in whatever the browser falls back to, under a
  // verdict of "clean" — the page asserting a drawing it never made.
  //
  // RIT publishes woff2 inside a GitLab release artifact and no stylesheet, so
  // it is the case that fails; asserting it here rather than on a Google family
  // is the whole point.
  for (const path of ["/font/rit-rachana/", "/font/rit-rachana/glyphs/", "/font/rit-rachana/lookups/"]) {
    test(`${path} loads the face it sets text in`, async ({ page }) => {
      await page.goto(`${BASE}${path}`);
      await page.evaluate(() => document.fonts.ready);

      const loaded = await page.evaluate(async (family) => {
        const unquote = (name) => name.replace(/^["']|["']$/g, "");
        const faces = [...document.fonts].filter(
          (face) => unquote(face.family) === family);
        if (!faces.length) return "no @font-face for it at all";
        await Promise.all(faces.map((face) => face.load().catch(() => {})));
        return faces.some((face) => face.status === "loaded") ? "" : "the file failed";
      }, "RIT Rachana");

      expect(loaded, `the page sets text in RIT Rachana but ${loaded}`).toBe("");
    });
  }
});
