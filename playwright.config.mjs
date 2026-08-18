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
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "node web/tests/serve.mjs",
    url: "http://127.0.0.1:8787/glyph-sleuth/",
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
});
