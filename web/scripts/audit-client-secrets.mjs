// Report locations and counts only. Never print matched values or credentials.
import { readdir, readFile } from "node:fs/promises";
import { join } from "node:path";

const privilegedName = /(?:SECRET|SERVICE[_-]?(?:ROLE|KEY)|ADMIN[_-]?KEY|DATABASE_URL|REDIS_URL|PASSWORD|PRIVATE_KEY|AUDIODB_API_KEY)/i;
const secrets = new Set(Object.entries(process.env)
  .filter(([key, value]) => privilegedName.test(key) && value && value.length >= 12)
  .map(([, value]) => value));
let environmentFiles = 0;
for (const file of ["../.env", "../.env.local", ".env", ".env.local", ".env.production", ".env.production.local"]) {
  try {
    const data = await readFile(file, "utf8");
    environmentFiles++;
    for (const line of data.split(/\r?\n/)) {
      const match = line.match(/^\s*(?:export\s+)?([\w]+)\s*=\s*(.*)$/);
      if (match && privilegedName.test(match[1])) {
        const value = match[2].replace(/^['"]|['"]$/g, "");
        if (value.length >= 12) secrets.add(value);
      }
    }
  } catch (error) { if (error.code !== "ENOENT") throw error; }
}

const findings = [];
let inspected = 0, sourceMaps = 0;
async function scan(directory) {
  for (const item of await readdir(directory, { withFileTypes: true })) {
    const file = join(directory, item.name);
    if (item.isDirectory()) { await scan(file); continue; }
    if (!/\.(?:js|css|map|html|json|svg|ts|tsx)$/.test(file)) continue;
    // Only public prerendered documents in the server output; server code is private.
    if (directory.startsWith(".next/server") && !file.endsWith(".html")) continue;
    inspected++;
    if (file.endsWith(".map")) sourceMaps++;
    const content = await readFile(file, "utf8");
    if ([...secrets].some((secret) => content.includes(secret) || content.includes(JSON.stringify(secret).slice(1, -1)))) {
      findings.push({ file, rule: "configured-privileged-value" });
    }
    if (/-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|postgres(?:ql)?(?:\+psycopg)?:\/\/[^\s"']+:[^\s"']+@|sb_secret_[A-Za-z0-9_-]{16,}/.test(content)) {
      findings.push({ file, rule: "privileged-credential-pattern" });
    }
    for (const token of content.match(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g) ?? []) {
      try {
        if (JSON.parse(Buffer.from(token.split(".")[1], "base64url").toString()).role === "service_role") {
          findings.push({ file, rule: "service-role-jwt" });
        }
      } catch { /* Not a JWT payload. */ }
    }
  }
}
for (const directory of [".next/static", ".next/server/app", "public", "src"]) await scan(directory);
console.log(JSON.stringify({ inspected, sourceMaps, environmentFiles, configuredPrivilegedValues: secrets.size, findings }, null, 2));
if (findings.length) process.exitCode = 1;
