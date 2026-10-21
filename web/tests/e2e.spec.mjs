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

// Character pages link a stylesheet per foundry family — twelve to smc.org.in on
// /char/0D15/ — and pull a font behind each. Browsers allow about six
// connections per host, so waiting for `load` means waiting for a third party
// to serve two dozen files, and it exceeded even a 90s timeout.
//
// What these tests actually need is the document and the font *registry*:
// `document.fonts` reports a FontFace as soon as its @font-face is parsed, and
// `fonts.ready` settles when the ones in use have resolved either way. Waiting
// for every image and every unused weight was never part of the assertion.
//
// The twelve requests are a real problem for a real reader too, not just for
// this suite — filed separately.
async function openWithFaces(page, path) {
  await page.goto(`${BASE}${path}`, { waitUntil: "domcontentloaded" });
  await page.evaluate(() => document.fonts.ready);
}

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

test.describe("Facets", () => {
  // Every facet button carries the number of rows it should show. The glyphs
  // page's three facets — encoded, built, unreachable — showed none at all from
  // the day they were added: the rows carry data-state, and the filter compared
  // every facet with data-verdict, which only the fonts index has. Clicking each
  // facet and counting what it shows catches that on any page with facets.
  for (const path of ["/fonts/", "/font/rachana/glyphs/"]) {
    test(`${path}: each facet shows the rows its count promises`, async ({ page }) => {
      await page.goto(`${BASE}${path}`);
      const facets = page.locator(".facet");
      const count = await facets.count();
      expect(count, "no facets here, so this proves nothing").toBeGreaterThan(1);
      for (let i = 0; i < count; i += 1) {
        const facet = facets.nth(i);
        const promised = Number(await facet.getAttribute("data-count"));
        await facet.click();
        const shown = await page.locator("table.index tbody tr").count();
        expect(shown, `"${await facet.textContent()}" promised ${promised}`).toBe(promised);
      }
    });
  }

  test("a block in the family's coverage table leads to its glyphs, and they add up", async ({ page }) => {
    // The table counts codepoints and the glyphs page lists glyphs, which agree
    // only because each glyph row names every codepoint it draws. Rachana's
    // coverage and glyph list are read from the same file, so they must match.
    await page.goto(`${BASE}/font/rachana/`);
    const row = page.locator("tr", { has: page.locator('a[href$="glyphs/?block=malayalam"]') });
    const [covered] = (await row.locator("td.mono").nth(1).textContent()).split("/").map(Number);
    const [first, last] = (await row.locator("td.mono").first().textContent())
      .split("–").map((code) => parseInt(code.replace("U+", ""), 16));
    await row.locator("a").click();
    await expect(page).toHaveURL(/glyphs\/\?block=malayalam/);

    const rows = page.locator("table.index tbody tr");
    const shown = await rows.count();
    expect(shown).toBeGreaterThan(0);
    await expect(page.locator('[data-block-note="malayalam"]')).toBeVisible();
    const codes = await rows.locator("td:nth-child(3) .mono").allTextContents();
    const inBlock = codes.map((code) => parseInt(code.replace("U+", ""), 16))
      .filter((cp) => cp >= first && cp <= last);
    expect(inBlock.length, "the block's glyphs do not add up to its coverage").toBe(covered);
  });

  test("a facet in the address is applied on arrival", async ({ page }) => {
    await page.goto(`${BASE}/font/rachana/glyphs/?facet=encoded`);
    const promised = Number(await page.locator('.facet[data-facet="encoded"]').getAttribute("data-count"));
    expect(promised).toBeGreaterThan(0);
    await expect(page.locator("table.index tbody tr")).toHaveCount(promised);
  });
});

test.describe("Try it in the address", () => {
  // "This sentence, in this family, at this size and weight, with akhn off" is a
  // link someone can be sent: every setting is kept, and read back on arrival.
  test("size, weight, italic and features survive the link", async ({ page }) => {
    const text = "മലയാളം";
    await page.goto(`${BASE}/font/rit-rachana/?text=${encodeURIComponent(text)}`
      + "&px=48&weight=700&italic=1&off=akhn,kern#try-it");
    const out = page.locator('[data-try="out"]');
    await expect(out).toBeVisible();
    const style = await out.evaluate((node) => {
      const s = getComputedStyle(node);
      return { size: s.fontSize, weight: s.fontWeight, italic: s.fontStyle,
               features: s.fontFeatureSettings };
    });
    expect(style).toMatchObject({ size: "48px", weight: "700", italic: "italic" });
    expect(style.features).toContain('"akhn" 0');
    expect(style.features).toContain('"kern" 0');
    await expect(page.locator('[data-feature="akhn"]')).not.toBeChecked();
    await expect(page.locator('[data-feature="blwf"]')).toBeChecked();

    // Changing one is written back, and a default leaves the address.
    await page.locator('[data-try="weight"]').selectOption("400");
    await page.locator('[data-feature="akhn"]').check();
    const url = new URL(page.url());
    expect(url.searchParams.get("weight")).toBeNull();
    expect(url.searchParams.get("off")).toBe("kern");
    expect(url.searchParams.get("px")).toBe("48");
  });

  test("a variable font's named styles and axes are offered, and kept", async ({ page }) => {
    // Nupuram is 33 named styles over four axes, and only weight and italic
    // were offered. Choosing one sets the font, and the link.
    const text = encodeURIComponent("മലയാളം");
    await page.goto(`${BASE}/font/nupuram/?text=${text}#try-it`);
    const out = page.locator('[data-try="out"]');
    await expect(out).toBeVisible();
    await page.locator('[data-try="style"]').selectOption({ label: "Condensed Bold" });
    const set = await out.evaluate((node) => {
      const s = getComputedStyle(node);
      return { weight: s.fontWeight, variation: s.fontVariationSettings };
    });
    expect(set.weight).toBe("700");
    expect(set.variation).toContain('"wdth" 75');
    const url = new URL(page.url());
    expect(url.searchParams.get("weight")).toBe("700");
    expect(url.searchParams.get("var")).toBe("wdth:75");

    // A link carrying a style arrives in it, and the menu names it.
    await page.goto(`${BASE}/font/nupuram/?text=${text}&var=SOFT:0#try-it`);
    await expect(page.locator('[data-try="style"] option:checked')).toHaveText("Sharp");
    expect(await page.locator('[data-try="out"]').evaluate((n) => getComputedStyle(n).fontVariationSettings))
      .toContain('"SOFT" 0');
  });

  test("a setting the family does not offer is ignored, not invented", async ({ page }) => {
    await page.goto(`${BASE}/font/rit-rachana/?text=a&px=5000&weight=950&off=zzzz`);
    const out = page.locator('[data-try="out"]');
    await expect(out).toBeVisible();
    const style = await out.evaluate((node) => getComputedStyle(node).fontSize);
    expect(style).toBe("96px");      // the slider's own maximum
    await expect(page.locator('[data-try="weight"]')).toHaveValue("400");
  });
});

test.describe("A shortlist in Inspect", () => {
  // Someone choosing a font types their text, sets it as they will use it,
  // picks and ranks families, and sends the link. The recipient must see that
  // shortlist, in that order and setting — and that the rest exist.
  const text = encodeURIComponent("മലയാളം");

  test("a sent shortlist arrives in its order and setting, with the rest one click away", async ({ page }) => {
    await page.goto(`${BASE}/inspect/?t=${text}&px=40&weight=700&italic=1&pick=rit-rachana,manjari,nosuchfamily`);
    const rows = page.locator(".shortlist .pick-row");
    await expect(rows).toHaveCount(2);
    expect(await rows.evaluateAll((all) => all.map((row) => row.dataset.row)))
      .toEqual(["rit-rachana", "manjari"]);
    await expect(page.locator("[data-shortlist]")).toContainText("Picked by whoever sent this link");
    // A pick this text cannot show is named, not silently dropped.
    await expect(page.locator("[data-shortlist]")).toContainText("nosuchfamily");
    // The rest are there, collapsed — never removed.
    await expect(page.locator("details.others")).not.toHaveAttribute("open", "");
    await expect(page.locator("details.others summary")).toContainText("families that have this text");

    // Set as sent, in a face the family really has, and nothing faked.
    const set = await rows.first().locator(".tile-glyph").evaluate((el) => {
      const s = getComputedStyle(el);
      return { size: s.fontSize, weight: s.fontWeight, style: s.fontStyle, synthesis: s.fontSynthesis };
    });
    expect(set).toMatchObject({ size: "40px", weight: "700", style: "italic" });
    expect(set.synthesis).toBe("none");
    // Its name leads to its Try it, with the same text and setting.
    const href = await rows.first().locator("a.draws").getAttribute("href");
    expect(href).toContain("/font/rit-rachana/?text=");
    expect(href).toMatch(/px=40.*weight=700.*italic=1#try-it/);
  });

  test("reordering and removing are written back to the link", async ({ page }) => {
    await page.goto(`${BASE}/inspect/?t=${text}&pick=rit-rachana,manjari`);
    await page.locator('.pick-row[data-row="rit-rachana"] [data-move="1"]').click();
    expect(new URL(page.url()).searchParams.get("pick")).toBe("manjari,rit-rachana");
    // Once changed, the picks are the reader's own, and the page says so.
    await expect(page.locator("[data-shortlist]")).toContainText("Your shortlist");
    await page.locator('.pick-row[data-row="manjari"] [data-drop]').click();
    expect(new URL(page.url()).searchParams.get("pick")).toBe("rit-rachana");
  });

  test("a row can be dragged into place with a finger", async ({ browser }) => {
    // The browser's own drag-and-drop never starts from a touch, so on a phone
    // the grip did nothing. Real touch events, in a phone-sized window.
    const context = await browser.newContext({ viewport: { width: 380, height: 800 },
      hasTouch: true, isMobile: true });
    const page = await context.newPage();
    await page.goto(`${BASE}/inspect/?t=${text}&pick=rit-rachana,manjari,gayathri`);
    const grip = page.locator('.pick-row[data-row="rit-rachana"] .grip');
    await expect(grip).toBeVisible();
    await grip.scrollIntoViewIfNeeded();
    const from = await grip.boundingBox();
    const last = await page.locator('.pick-row[data-row="gayathri"]').boundingBox();
    const x = from.x + from.width / 2;
    const cdp = await context.newCDPSession(page);
    const touch = (type, y) => cdp.send("Input.dispatchTouchEvent", {
      type, touchPoints: type === "touchEnd" ? [] : [{ x, y }] });
    await touch("touchStart", from.y + from.height / 2);
    for (let y = from.y; y <= last.y + last.height - 4; y += 12) await touch("touchMove", y);
    await touch("touchEnd");
    await expect.poll(() => new URL(page.url()).searchParams.get("pick"))
      .toBe("manjari,gayathri,rit-rachana");
    await context.close();
  });

  test("matching sets each family so its letters stand as tall as the others", async ({ page }) => {
    // At one font size Nupuram looked twice Karumbi's height: a size is the
    // em box, not the letters in it. Matched, the ink heights agree.
    await page.goto(`${BASE}/inspect/?t=${text}&px=40&match=1&pick=nupuram,karumbi`);
    const rows = page.locator(".shortlist .pick-row");
    await expect(rows.nth(0).locator(".draws-short")).toContainText("to match", { timeout: 15_000 });
    await expect(rows.nth(1).locator(".draws-short")).toContainText("to match", { timeout: 15_000 });
    const tall = await rows.locator(".tile-glyph").evaluateAll((spans) => spans.map((span) => {
      const style = getComputedStyle(span);
      const ruler = document.createElement("canvas").getContext("2d");
      ruler.font = `${style.fontStyle} ${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
      // The median ink height of the text's clusters: what matching promises.
      const tall = [...new Intl.Segmenter(undefined, { granularity: "grapheme" })
        .segment(span.textContent)].map(({ segment }) => {
        const box = ruler.measureText(segment);
        return box.actualBoundingBoxAscent + box.actualBoundingBoxDescent;
      }).filter((h) => h > 0).sort((x, y) => x - y);
      return tall[tall.length >> 1];
    }));
    const [a, b] = tall;
    expect(Math.abs(a - b) / Math.max(a, b), `ink heights ${a} and ${b}`).toBeLessThan(0.15);
    // And the sizes it took differ, which is the point.
    const sizes = await rows.locator(".tile-glyph").evaluateAll((spans) =>
      spans.map((span) => getComputedStyle(span).fontSize));
    expect(sizes[0]).not.toBe(sizes[1]);
  });

  test("a pick's own size is kept in the link and said on the row", async ({ page }) => {
    await page.goto(`${BASE}/inspect/?t=${text}&pick=rit-rachana,manjari`);
    const own = page.locator('.pick-row[data-row="manjari"] [data-own="px"]');
    await own.fill("58");
    await own.dispatchEvent("change");
    expect(new URL(page.url()).searchParams.get("pick")).toBe("rit-rachana,manjari:58px");
    const row = page.locator('.pick-row[data-row="manjari"]');
    await expect(row.locator(".draws-short")).toHaveText("58px, set by hand");
    expect(await row.locator(".tile-glyph").evaluate((el) => getComputedStyle(el).fontSize)).toBe("58px");
    // And a link carrying it arrives with it.
    await page.goto(`${BASE}/inspect/?t=${text}&pick=manjari:44px`);
    await expect(page.locator('[data-own="px"]')).toHaveValue("44");
  });

  test("a shortlisted family can be set in one of its own styles", async ({ page }) => {
    await page.goto(`${BASE}/inspect/?t=${text}&pick=nupuram,manjari`);
    const style = page.locator('.pick-row[data-row="nupuram"] [data-own="style"]');
    await style.selectOption({ label: "Sharp" });
    expect(new URL(page.url()).searchParams.get("pick")).toMatch(/^nupuram:.*SOFT=0.*,manjari$/);
    const glyph = page.locator('.pick-row[data-row="nupuram"] .tile-glyph');
    expect(await glyph.evaluate((el) => getComputedStyle(el).fontVariationSettings)).toContain('"SOFT" 0');
    // A family with no styles of its own offers none.
    await expect(page.locator('.pick-row[data-row="manjari"] [data-own="style"]')).toHaveCount(0);
  });

  test("a weight a family does not publish is not faked, and is said", async ({ page }) => {
    await page.goto(`${BASE}/inspect/?t=${text}&weight=900&pick=rit-rachana`);
    const row = page.locator('.pick-row[data-row="rit-rachana"]');
    await expect(row.locator(".draws-short")).toHaveText("no 900, set at 700");
    expect(await row.locator(".tile-glyph").evaluate((el) => getComputedStyle(el).fontWeight)).toBe("700");
  });

  test("a star on a family's tile adds it to the shortlist and the link", async ({ page }) => {
    await page.goto(`${BASE}/inspect/?t=${text}`);
    await expect(page.locator(".shortlist")).toHaveCount(0);
    await page.locator('.pick[data-pick="rit-rachana"]').click();
    await expect(page.locator('.pick-row[data-row="rit-rachana"]')).toBeVisible();
    await expect(page.locator('.pick[data-pick="rit-rachana"]')).toHaveAttribute("aria-pressed", "true");
    expect(new URL(page.url()).searchParams.get("pick")).toBe("rit-rachana");
    await page.locator('[data-set="weight"]').selectOption("700");
    expect(new URL(page.url()).searchParams.get("weight")).toBe("700");
  });
});

test.describe("Marks on their circle", () => {
  // Inspect draws a mark on a dotted circle. With the page font, which has
  // neither, Firefox took the circle from one fallback font and the mark from
  // another, whose shaper added a second circle. One face must draw both.
  test("Inspect draws a mark and its circle in one face that has both @firefox", async ({ page }) => {
    await page.goto(`${BASE}/inspect/?t=${encodeURIComponent("സിബു")}`);
    const cell = page.locator("td[data-mark]").first();
    await expect(cell).toHaveAttribute("data-drawn", "", { timeout: 15_000 });
    await expect(cell).toBeVisible();
    const drawn = await cell.evaluate((el) => {
      const family = el.style.fontFamily.split(",")[0].trim().replace(/^"|"$/g, "");
      return { family, has: family && document.fonts.check(`30px "${family}"`, el.textContent.trim()) };
    });
    expect(drawn.family, "the mark was left to fallback fonts").not.toBe("");
    expect(drawn.has, `${drawn.family} is not loaded for the circle and the mark`).toBe(true);
  });
});

test.describe("Links into a page", () => {
  test("copy link copies this page's address with the section", async ({ page, context }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    await page.goto(`${BASE}/script/Latn/`);
    const button = page.locator("#families .section-link");
    await button.click();
    const copied = await page.evaluate(() => navigator.clipboard.readText());
    expect(copied).toMatch(/\/script\/Latn\/#families$/);
    await expect(page).toHaveURL(/#families$/);
    await expect(button).toHaveText("copied");
  });

  test("a link to a section lands on it", async ({ page }) => {
    await page.goto(`${BASE}/script/Latn/#families`);
    await expect(page.locator("#families")).toBeInViewport();
  });

  test("Inspect's sections can be linked to once they are drawn", async ({ page }) => {
    // They exist only after the text is read, so the browser's own jump to the
    // fragment found nothing; Inspect makes it once they do.
    await page.goto(`${BASE}/inspect/?t=U%2B0D7B#families`);
    await expect(page.locator("#families")).toBeInViewport({ timeout: 15_000 });
    await expect(page.locator("#families .section-link")).toBeVisible();
  });

  test("an index filter is in the address and comes back from it", async ({ page }) => {
    await page.goto(`${BASE}/languages/`);
    const total = Number((await page.locator("[data-showing]").textContent()).replace(/,/g, ""));
    await page.locator(".filter").fill("abkhaz");
    await expect(page).toHaveURL(/[?&]q=abkhaz/);

    await page.goto(`${BASE}/languages/?q=abkhaz`);
    await expect(page.locator(".filter")).toHaveValue("abkhaz");
    const shown = Number((await page.locator("[data-showing]").textContent()).replace(/,/g, ""));
    expect(shown).toBeGreaterThan(0);
    expect(shown).toBeLessThan(total);
  });

  test("a script is found by a language written in it", async ({ page }) => {
    // #86: "Chinese" found nothing, because the rows named scripts.
    await page.goto(`${BASE}/scripts/?q=chinese`);
    const shown = page.locator("table.index tbody tr");
    await expect(shown.first()).toBeVisible();
    await expect(shown.filter({ has: page.locator('a[href$="/script/Hani/"]') })).toHaveCount(1);
  });

  test("Try it's line is in the address and previews on arrival", async ({ page }) => {
    await page.goto(`${BASE}/font/manjari/?text=${encodeURIComponent("ക്ക")}#try-it`);
    await expect(page.locator('[data-try="out"]')).toBeVisible();
    await expect(page.locator('[data-try="out"]')).toContainText("ക്ക");
    await expect(page.locator("#try-it")).toBeInViewport();
  });
});

test.describe("Home", () => {
  test("the box on the home page opens Inspect with what was typed", async ({ page }) => {
    // A plain GET form, so it works before any script has run.
    await page.goto(`${BASE}/`);
    await page.locator("#ask-t").fill("U+0D7B");
    await page.locator(".ask button").click();
    await expect(page).toHaveURL(/\/inspect\/\?t=U%2B0D7B/);
    await expect(page.locator("#inspect-out")).toContainText("MALAYALAM LETTER CHILLU N");
  });

  test("every example on the home page is drawn by the face it names", async ({ page }) => {
    // The cases name a family under each drawing; the chips name none and are
    // set in the family that draws them correctly. A face that did not arrive
    // would leave the browser drawing a broken example under a good verdict.
    await page.goto(`${BASE}/`);
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(1500);
    await expect(page.locator(".case-glyph.fallback")).toHaveCount(0);
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

  test("the r12a String Analyser link opens with the text in it", async ({ page }) => {
    // It passed ?text=, which the analyser does not read, so it opened empty.
    // It reads ?chars=, on index.html.
    await page.goto(`${BASE}/inspect/?t=${encodeURIComponent("സിബു")}`);
    const link = page.locator("#inspect-out a", { hasText: "r12a String Analyser" });
    await expect(link).toHaveAttribute("href",
      "https://r12a.github.io/app-analysestring/index.html?chars=%E0%B4%B8%E0%B4%BF%E0%B4%AC%E0%B5%81");
  });

  test("a second number does not change what the first one means", async ({ page }) => {
    // "2018" was U+2018 and "2018 2" was U+07E2 and U+0002: in a list, bare
    // digits were read as decimal. They are hex alone and hex in a list now.
    await page.goto(`${BASE}/inspect/?t=2018%202`);
    const out = page.locator("#inspect-out");
    await expect(out).toContainText("U+2018");
    await expect(out).toContainText("LEFT SINGLE QUOTATION MARK");
    await expect(out).not.toContainText("U+07E2");
    // Decimal is still one step away, in its own notation.
    await page.goto(`${BASE}/inspect/?t=${encodeURIComponent("&#2018;")}`);
    await expect(page.locator("#inspect-out")).toContainText("U+07E2");
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

  test("offers every family the character page does", async ({ page }) => {
    // Inspect showed eight families of ten per block while /char/0D7B/ listed
    // every family with the chillu. Asked about the same codepoint, the two
    // pages must now offer the same families.
    await page.goto(`${BASE}/char/0D7B/`);
    const onChar = await page.locator(".drawn .draws-name").allTextContents();
    await page.goto(`${BASE}/inspect/?t=U%2B0D7B`);
    await page.locator("#drawn-by .draws").first().waitFor();
    const onInspect = await page.locator("#drawn-by .draws-name").allTextContents();
    const bare = (names) => names.map((name) => name.replace(/ ·$/, "")).sort();
    expect(bare(onInspect)).toEqual(bare(onChar));
    // And it says it is all of them, rather than leaving a count to be guessed.
    await expect(page.locator("#drawn-by")).toContainText(`All ${onChar.length}`);
  });

  test("a family missing one codepoint of the text is not offered", async ({ page }) => {
    // ഞ്ഞ് is NYA and the virama, twice. The families offered are exactly those
    // on both characters' own pages — no fewer, as under the old cap of eight,
    // and none that has only one of the two.
    const familiesOf = async (path) => {
      await page.goto(`${BASE}${path}`);
      return new Set(await page.locator(".drawn .draws-name").allTextContents());
    };
    const nya = await familiesOf("/char/0D1E/");
    const virama = await familiesOf("/char/0D4D/");
    const both = [...nya].filter((name) => virama.has(name)).sort();

    await page.goto(`${BASE}/inspect/?t=%E0%B4%9E%E0%B5%8D%E0%B4%9E%E0%B5%8D`);
    await page.locator("#drawn-by .draws").first().waitFor();
    const offered = (await page.locator("#drawn-by .draws-name").allTextContents())
      .map((name) => name.replace(/ ·$/, "")).sort();
    expect(offered).toEqual(both);
  });

  test("a slow foundry stylesheet is waited for, not reported missing", async ({ page }) => {
    // Every Inspect tile loads its face lazily. lazyfaces.js appended a foundry's
    // <link> and checked the face on `document.fonts.ready`, which knows nothing
    // of a stylesheet still in flight — so when SMC's server was slow, all of
    // its families were marked as not drawing text they drew. Make it slow.
    await page.route(/smc\.org\.in\/.*\.css/, async (route) => {
      await new Promise((settle) => setTimeout(settle, 2500));
      await route.continue();
    });
    await page.goto(`${BASE}/inspect/?t=%E0%B4%9E%E0%B5%8D%E0%B4%9E%E0%B5%8D`);
    // Faces load as they are scrolled to, so go to it rather than hope it is near.
    await page.locator('#drawn-by .drawn .tile-glyph[data-slug="manjari"]').scrollIntoViewIfNeeded();
    const smc = page.locator('#drawn-by .tile-glyph[data-face="Manjari"]');
    await smc.waitFor({ timeout: 15_000 });
    // The check runs after promotion; a negative has to be given time to fail.
    await page.waitForTimeout(2000);
    await expect(page.locator("#drawn-by .tile-glyph.fallback")).toHaveCount(0);
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

  test("the weights on offer are real files, not a smeared regular", async ({ page }) => {
    // Foundry families had no weight control at all: we read one face from the
    // release, so we did not know a second existed. Now every face ships, and
    // the thing to prove is that each option is backed by a face that loaded
    // rather than by the browser smearing the regular.
    //
    // The obvious proxy — heavier draws wider — is not a law, and CI caught me
    // assuming it was: weight and advance width need not correlate at all, and
    // metric-compatible families keep every weight the same width deliberately.
    // So this asks the font system directly. A FontFace with that weight, for
    // this family, in state "loaded" is the fact; how wide it drew is not.
    //
    // Which family answers this is the index's business; that a foundry family
    // *can* have a weight control is pinned in test_render, against markup.
    // The family is found, not named. Charis is "Charis" in a small build and
    // "Charis SIL" in the full one — its own release decides — so a hard-coded
    // slug passes locally and 404s in CI, which is exactly what it did.
    await page.goto(`${BASE}/fonts/`);
    // Not any family with a weight control: a Google one gets its faces from
    // Google's own stylesheet and would pass this while our @font-face rules
    // were entirely broken. The row's data-source says which are ours, and those
    // are the ones whose descriptors this build writes.
    const slugs = await page.locator("table.index tr:not([data-source='google']) a[href*='/font/']")
      .evaluateAll((nodes) => nodes.map((node) => node.getAttribute("href")).slice(0, 60));
    expect(slugs.length, "no family outside Google is indexed").toBeGreaterThan(0);

    let found = null;
    for (const href of slugs) {
      const body = await (await page.request.get(href)).text();
      if (body.includes('data-try="weight"') && body.includes("/webfonts/")) {
        found = href;
        break;
      }
    }
    expect(found, "no family we serve ourselves offers a weight control").not.toBeNull();

    await page.goto(found);
    await page.evaluate(() => document.fonts.ready);
    const weights = await page.locator('[data-try="weight"] option').evaluateAll(
      (nodes) => nodes.map((node) => node.value));
    await page.fill('[data-try="text"]', "Weights and styles");
    await page.click('[data-try="go"]');
    await expect(page.locator(".try-out")).toBeVisible();

    expect(weights.length, "a weight control with one option is not a control")
      .toBeGreaterThan(1);

    const family = await page.locator(".try").getAttribute("data-face");
    for (const weight of weights) {
      await page.selectOption('[data-try="weight"]', weight);
      await page.waitForFunction(() => document.fonts.status === "loaded");

      const served = await page.evaluate(([name, want]) => {
        const unquote = (value) => value.replace(/^["']|["']$/g, "");
        return [...document.fonts]
          .filter((face) => unquote(face.family) === name && face.status === "loaded")
          // A variable face carries a range — "100 900" — and covers every
          // weight inside it from the one file, which is not a fake bold.
          .some((face) => {
            const bounds = String(face.weight).split(/\s+/).map(Number);
            return bounds.length > 1
              ? want >= bounds[0] && want <= bounds[1]
              : bounds[0] === want;
          });
      }, [family, Number(weight)]);

      expect(served, `${family} offers weight ${weight} and loaded no such face`).toBe(true);
    }

    // And where an italic is offered it is the family's own italic face.
    const italic = page.locator('[data-try="italic"]');
    if (await italic.count()) {
      await italic.check();
      await page.waitForFunction(() => document.fonts.status === "loaded");
      const style = await page.locator(".try-out").evaluate(
        (node) => getComputedStyle(node).fontStyle);
      expect(style).toBe("italic");
    }
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

test.describe("faces arrive as you scroll", () => {
  // U+0041 is covered by a hundred families in a small build and nine hundred in
  // the full one, so it is the page this exists for.
  test("every family has a tile, and only the drawn ones claim to be", async ({ page }) => {
    await openWithFaces(page, "/char/0041/");
    const tiles = page.locator(".tile-glyph");
    const total = await tiles.count();
    expect(total, "the page should carry every covering family").toBeGreaterThan(30);

    // On load: a first batch claiming a face, the rest waiting and claiming
    // nothing. A tile without its face has not been drawn by the family it
    // names, and app.js must not mark it as failed.
    await page.evaluate(() => document.fonts.ready);
    const claimed = await page.locator(".tile-glyph[data-face]").count();
    const waiting = await page.locator(".tile-glyph[data-family]").count();
    expect(claimed).toBeGreaterThan(0);
    expect(waiting).toBeGreaterThan(0);
    expect(claimed + waiting).toBe(total);

    // The one that would be a disaster: eight hundred families cried wolf over.
    await page.waitForTimeout(1200);
    expect(await page.locator(".tile-glyph.fallback").count(),
      "a tile still waiting for its face was marked as failed").toBe(0);
  });

  test("scrolling loads more, and does not cry wolf about them", async ({ page }) => {
    await openWithFaces(page, "/char/0041/");
    const waitingAtFirst = await page.locator(".tile-glyph[data-family]").count();
    expect(waitingAtFirst, "nothing was left to load, so this proves nothing")
      .toBeGreaterThan(0);

    // Scroll the window, not the element: Playwright's scrollIntoViewIfNeeded
    // left scrollY at 0 here, so the observer never fired and the test proved
    // nothing while passing its other assertion.
    //
    // Then wait for a condition rather than a duration. Comparing a before/after
    // count across a fixed sleep passed alone and failed inside the full suite,
    // because how many faces land in 2.5s depends on what else is running.
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForFunction(
      (was) => document.querySelectorAll(".tile-glyph[data-family]").length < was,
      waitingAtFirst, { timeout: 15000 });

    // A *proportion*, not zero. This asserted zero and failed on the full
    // corpus with six marked out of about 1,830 — and six third-party
    // stylesheets out of eighteen hundred not arriving is ordinary. The marking
    // flagging them is the honesty feature working, not a bug.
    //
    // Zero was the same species of mistake as "heavier weights draw wider": a
    // premise that felt like a law and is not one. What is worth asserting is
    // that the loader is not *systematically* broken — if a batch request were
    // malformed, twenty families would fail together, and if the promotion
    // ordering regressed, hundreds would.
    //
    // It names them on failure so the next person has the answer in the log
    // rather than in a downloaded trace, which is how this one had to be
    // diagnosed.
    const claimed = await page.locator(".tile-glyph[data-face]").count();
    const marked = await page.locator(".tile-glyph.fallback").evaluateAll(
      (nodes) => nodes.map((node) => node.dataset.face));
    expect(marked.length / Math.max(claimed, 1),
      `${marked.length} of ${claimed} faces marked as absent — a handful is `
      + `ordinary, this many suggests the loader itself: ${marked.slice(0, 12).join(", ")}`)
      .toBeLessThan(0.05);
  });

  test("a lazily-loaded face that never arrives is still marked", async ({ page }) => {
    // The gap this closes: app.js runs its check once on load, and these tiles
    // are only promoted to claims afterwards — so for a while a lazy face that
    // failed to arrive was presented as a drawing, silently. The eager path has
    // always had a test for exactly this; the lazy path needed its own.
    //
    // Every webfont request is blocked, so no lazy face can possibly arrive.
    await page.route("**/*.woff2", (route) => route.abort());
    await page.route("https://fonts.googleapis.com/**", (route) => route.abort());

    await openWithFaces(page, "/char/0041/");
    // The faces in the markup, before any scrolling: whatever DRAWN_LIMIT is.
    const eager = await page.locator(".tile-glyph[data-face]").count();
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(2500);

    const promoted = await page.locator(".tile-glyph[data-face]").count();
    const marked = await page.locator(".tile-glyph.fallback").count();
    expect(promoted, "nothing was promoted, so this proves nothing").toBeGreaterThan(eager);
    expect(marked, "a face that never arrived was presented as a drawing")
      .toBeGreaterThan(0);
    // And the panel says so once, not once per tile.
    expect(await page.locator(".fallback-note").count()).toBe(1);
  });

  test("with JavaScript off every family is still listed", async ({ browser }) => {
    // The tiles are the cheap part and they are in the markup. What a reader
    // without JavaScript loses is the drawing of the later ones, not the answer
    // to "which families have this character".
    const context = await browser.newContext({ javaScriptEnabled: false });
    const page = await context.newPage();
    await openWithFaces(page, "/char/0041/");
    expect(await page.locator(".tile-glyph").count()).toBeGreaterThan(30);
    expect(await page.locator(".draws-name").count()).toBeGreaterThan(30);
    await context.close();
  });
});

test.describe("a face that is drawing is not marked as absent", () => {
  test("families on a character page render it", async ({ page }) => {
    // The bug this exists for: Dyuthi was marked as not drawing ക, which it
    // draws perfectly well. A false positive here is worse than no check at all,
    // because it tells a reader a working font is broken.
    await openWithFaces(page, "/char/0D15/");
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
    await openWithFaces(page, "/char/0D15/");

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

  for (const path of ["/", "/fonts/", "/feature/", "/font/manjari/", "/char/0D15/", "/inspect/?t=%E0%B4%95"]) {
    test(`${path} does not scroll sideways`, async ({ page }) => {
      // domcontentloaded, not load. A character page links twelve stylesheets
      // from one foundry host and pulls a font behind each; browsers allow about
      // six connections per host, so waiting for every one of them made this
      // test hostage to smc.org.in and it timed out at 30s. What it measures is
      // the layout of containers — the faults it has actually caught were a wide
      // table, a menu hanging off the edge and a grid child sized by an
      // unbreakable code snippet, none of which need a webfont to show up.
      await page.goto(`${BASE}${path}`, { waitUntil: "domcontentloaded" });
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
