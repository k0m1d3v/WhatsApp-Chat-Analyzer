// Zip reading and AI request shapes for the browser code, with fetch replaced by a fake.
import { readFileSync } from "node:fs";
import assert from "node:assert/strict";
import { chatFromZip, isZip } from "../site/js/zip.js";
import { parse } from "../site/js/parser.js";
import { compute } from "../site/js/stats.js";
import { analyze } from "../site/js/ai.js";
import { renderReport } from "../site/js/report.js";

const zip = new Uint8Array(readFileSync(new URL("./fixtures/export.zip", import.meta.url)));
assert.ok(isZip(zip));
const text = await chatFromZip(zip);
const lf = (t) => t.replace(/\r\n/g, "\n"); // exports can use either line ending
assert.equal(lf(text), lf(readFileSync(new URL("./fixtures/android_it_12h.txt", import.meta.url), "utf-8")));

const messages = parse(text);
const stats = compute(messages);
const calls = [];
globalThis.fetch = async (url, init) => {
  calls.push({ url, headers: init.headers, body: JSON.parse(init.body) });
  const json = { vibe: "Person A <img src=x onerror=alert(1)>", topics: [], moments: [], people: [{ name: "Person A", description: "d" }], closing: "c" };
  const payload = url.includes("anthropic")
    ? { stop_reason: "end_turn", content: [{ type: "text", text: JSON.stringify(json) }] }
    : { choices: [{ message: { content: JSON.stringify(json) } }] };
  return new Response(JSON.stringify(payload), { status: 200 });
};

const r = await analyze("wrapped", stats, messages, { provider: "claude", key: "test-key", anonymize: true });
const c = calls[0];
assert.equal(c.url, "https://api.anthropic.com/v1/messages");
assert.equal(c.headers["x-api-key"], "test-key");
assert.equal(c.headers["anthropic-dangerous-direct-browser-access"], "true");
assert.equal(c.body.model, "claude-opus-5-5");
assert.equal(c.body.output_config.format.type, "json_schema");
const sent = c.body.messages[0].content;
for (const name of ["Luca", "Bianchi", "Anna", "Marta"]) assert.ok(!sent.includes(name), `${name} leaked`);
assert.ok(sent.includes("[link]"));
assert.equal(r.people[0].name, "Luca Bianchi"); // aliases mapped back

await analyze("profile", stats, messages, { provider: "openai", key: "test-key", anonymize: false, person: "Anna" });
assert.equal(calls[1].url, "https://api.openai.com/v1/chat/completions");
assert.equal(calls[1].headers.authorization, "Bearer test-key");
assert.equal(calls[1].body.response_format.json_schema.strict, true);
assert.ok(calls[1].body.messages[1].content.includes("communication style of Anna"));

const html = renderReport(stats, "T", { aiWrapped: r });
assert.ok(!html.includes("<img src=x"), "AI text must be escaped");

globalThis.fetch = async () => new Response(JSON.stringify({ error: { message: "bad key" } }), { status: 401 });
await assert.rejects(analyze("wrapped", stats, messages, { provider: "claude", key: "x" }), /not valid/);
console.log("ok");
