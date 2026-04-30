import http from "http";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DIST_DIR = path.join(__dirname, "dist");
const PORT = 3000;

const MIME_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
  ".ttf": "font/ttf",
  ".eot": "application/vnd.ms-fontobject",
  ".webp": "image/webp",
};

process.on("uncaughtException", (err) => {
  console.error("[uncaughtException]", err);
});

process.on("unhandledRejection", (reason) => {
  console.error("[unhandledRejection]", reason);
});

const server = http.createServer((req, res) => {
  try {
    // Strip query string
    const urlPath = req.url.split("?")[0];
    let filePath = path.join(DIST_DIR, urlPath);

    // Prevent directory traversal outside dist/
    if (!filePath.startsWith(DIST_DIR)) {
      res.writeHead(403);
      res.end("Forbidden");
      return;
    }

    // If the path is a directory, look for index.html inside it
    try {
      if (fs.existsSync(filePath) && fs.statSync(filePath).isDirectory()) {
        filePath = path.join(filePath, "index.html");
      }
    } catch (statErr) {
      console.error(`[stat error] ${filePath}:`, statErr);
    }

    // Serve the file if it exists, otherwise fall back to index.html (SPA routing)
    try {
      if (!fs.existsSync(filePath)) {
        filePath = path.join(DIST_DIR, "index.html");
      }
    } catch (existsErr) {
      console.error(`[existsSync error] ${filePath}:`, existsErr);
      filePath = path.join(DIST_DIR, "index.html");
    }

    const ext = path.extname(filePath).toLowerCase();
    const contentType = MIME_TYPES[ext] || "application/octet-stream";

    fs.readFile(filePath, (err, data) => {
      if (err) {
        console.error(`[readFile error] ${filePath}:`, err);
        if (!res.headersSent) {
          res.writeHead(500);
          res.end("Internal Server Error");
        }
        return;
      }
      res.writeHead(200, { "Content-Type": contentType });
      res.end(data);
    });
  } catch (err) {
    console.error(`[request handler error] ${req.method} ${req.url}:`, err);
    if (!res.headersSent) {
      res.writeHead(500);
      res.end("Internal Server Error");
    }
  }
});

server.on("error", (err) => {
  console.error("[server error]", err);
});

server.listen(PORT, "0.0.0.0", () => {
  console.log(`Serving dist/ on http://0.0.0.0:${PORT}`);
});
