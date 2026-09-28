import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { Script } from "node:vm";

const get = (path) => readFileSync(new URL("../" + path, import.meta.url), "utf8");
const areas = JSON.parse(get("data/research-areas.json"));
const refs = JSON.parse(get("data/scientisttwo-reference.json"));
const html = get("index.html");
const js = get("assets/app.js");

assert.equal(areas.length, 8, "Twinaper needs exactly eight geospatial fields");
assert.equal(new Set(areas.map((d) => d.id)).size, 8);
assert.ok(areas.every((d) => d.name && d.search && d.example));
assert.equal(refs.length, 86, "Reference gallery must contain 86 ORIGINAL ScientistTwo papers");
assert.equal(new Set(refs.map((r) => r.id)).size, 86);
const counts = Object.fromEntries(
  ["applications","deep_learning","general_ml","optimization","probabilistic","rl","social_aspects","theory"]
    .map((domain) => [domain, refs.filter((r) => r.domain === domain).length])
);
assert.deepEqual(counts, {
  applications: 15, deep_learning: 24, general_ml: 14, optimization: 5,
  probabilistic: 10, rl: 3, social_aspects: 9, theory: 6
});
assert.ok(refs.every((r) =>
  r.source === "ScientistTwo" && r.kind === "external-reference"
  && r.url.startsWith("https://scientist-two.github.io/generated-papers/")
  && r.url.endsWith(".pdf")
), "External references cannot be represented as Twinaper outputs");
assert.ok(html.includes('id="research-form"') && html.includes('src="assets/app.js"'));
assert.ok(html.includes('id="reference-grid"') && html.includes('id="map"'));
assert.ok(existsSync(new URL("../assets/style.css", import.meta.url)));
assert.ok(existsSync(new URL("../researcher.py", import.meta.url)));
new Script(js, {filename: "assets/app.js"});
console.log("PASS: 8 GeoAI fields; 86 attributed references in 8 ORIGINAL AI domains.");
console.log("PASS: unique references, valid PDF URLs, expected UI elements and valid JavaScript syntax.");
