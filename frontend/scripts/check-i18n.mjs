// Fails when hi.json or mr.json does not have exactly the same keys as en.json.
// Hindi and Marathi are mandatory for the homeowner journey (ARCHITECTURE §2), so a
// missing translation is a build error, not a fallback.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const dir = new URL("../messages/", import.meta.url);
const load = (locale) => JSON.parse(readFileSync(fileURLToPath(new URL(`${locale}.json`, dir)), "utf8"));

function flatten(obj, prefix = "") {
  return Object.entries(obj).flatMap(([key, value]) => {
    if (!prefix && key === "_meta") return [];
    const path = prefix ? `${prefix}.${key}` : key;
    return value && typeof value === "object" ? flatten(value, path) : [path];
  });
}

const base = new Set(flatten(load("en")));
let failed = false;
for (const locale of ["hi", "mr"]) {
  const keys = new Set(flatten(load(locale)));
  const missing = [...base].filter((k) => !keys.has(k));
  const extra = [...keys].filter((k) => !base.has(k));
  if (missing.length || extra.length) {
    failed = true;
    for (const k of missing) console.error(`[${locale}] missing: ${k}`);
    for (const k of extra) console.error(`[${locale}] extra:   ${k}`);
  }
}
if (failed) process.exit(1);
console.log(`i18n OK: ${base.size} keys in en, hi, mr`);
