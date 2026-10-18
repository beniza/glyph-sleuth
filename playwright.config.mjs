// Live tests against the built site, served the way GitHub Pages serves it.
//
// The site is generated for /glyph-sleuth/, so it has to be served under that
// path or every absolute URL in it 404s — which is itself a bug we shipped once.
// The server maps that prefix onto site/ and refuses to invent anything else, so
// a missing page fails here exactly as it would in production.
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "web/tests",
  testMatch: /e2e.*\.mjs$/,
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : [["list"]],
  use: {
    baseURL: "http://127.0.0.1:8787",
    trace: process.env.CI ? "retain-on-failure" : "off",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    // Firefox falls back font by font where Chrome falls back by cluster, which
    // is how a mark on its dotted circle came out with two circles there and one
    // here. Only the tests tagged @firefox run in it: the rest would double the
    // deploy's test time to check what Chromium already checks.
    { name: "firefox", use: { ...devices["Desktop Firefox"] }, grep: /@firefox/ },
  ],
  webServer: {
    command: "node web/tests/serve.mjs",
    url: "http://127.0.0.1:8787/glyph-sleuth/",
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
});
