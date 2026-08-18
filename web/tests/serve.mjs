// Serve site/ the way GitHub Pages serves it: under /glyph-sleuth/, with
// directory URLs resolving to index.html and anything missing returning 404.
//
// Serving from the root instead would make every absolute URL in the pages
// resolve by accident, and hide exactly the class of bug that shipped once —
// a stylesheet and a wordmark pointing at the domain root.
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../site");
const PREFIX = "/glyph-sleuth";
const PORT = 8787;

const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".txt": "text/plain; charset=utf-8",
  ".woff2": "font/woff2",
};

http.createServer((request, response) => {
  const url = new URL(request.url, `http://${request.headers.host}`);
  if (!url.pathname.startsWith(PREFIX)) {
    response.writeHead(404).end("outside the site's own path");
    return;
  }
  let target = path.join(ROOT, decodeURIComponent(url.pathname.slice(PREFIX.length)));
  // Keep the server inside the site directory whatever the request says.
  if (!target.startsWith(ROOT)) {
    response.writeHead(403).end("no");
    return;
  }
  if (fs.existsSync(target) && fs.statSync(target).isDirectory()) {
    target = path.join(target, "index.html");
  }
  if (!fs.existsSync(target)) {
    response.writeHead(404, { "content-type": "text/plain" }).end("not built");
    return;
  }
  response.writeHead(200, {
    "content-type": TYPES[path.extname(target)] || "application/octet-stream",
  });
  fs.createReadStream(target).pipe(response);
}).listen(PORT, "127.0.0.1", () => {
  console.log(`serving site/ at http://127.0.0.1:${PORT}${PREFIX}/`);
});
