/* Identificador reproducible de cada versión del frontend. */
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const root = path.resolve(__dirname, "..");
const digest = crypto.createHash("sha256");
const files = [];
for (const folder of ["app", "components", "lib", "public"]) {
  function walk(relative) {
    for (const entry of fs.readdirSync(path.join(root, relative), { withFileTypes: true })) {
      const name = path.posix.join(relative, entry.name);
      if (entry.isDirectory()) walk(name);
      else if (entry.isFile() && name !== "app/release.json") files.push(name);
    }
  }
  walk(folder);
}
for (const name of ["package-lock.json", "next.config.ts", "Dockerfile", "scripts/generate-release.cjs"]) {
  if (fs.existsSync(path.join(root, name))) files.push(name);
}
for (const name of files.sort()) {
  digest.update(name);
  digest.update("\0");
  digest.update(fs.readFileSync(path.join(root, name)));
  digest.update("\0");
}
const revision = "v1-" + digest.digest("hex").slice(0, 20);
fs.writeFileSync(path.join(root, "app", "release.json"), JSON.stringify({ revision }) + "\n");
console.log("VIEWTV_FRONTEND_RELEASE=" + revision);
