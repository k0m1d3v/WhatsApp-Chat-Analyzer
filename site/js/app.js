// Page logic: load a chat, render the report, optional AI. Nothing is uploaded except the AI request.

import { parse } from "./parser.js";
import { isZip, chatFromZip } from "./zip.js";
import { compute, filterMessages } from "./stats.js";
import { renderReport, reportDocument, REPORT_CSS } from "./report.js";
import { analyze, DEFAULT_MODELS } from "./ai.js";

const $ = (id) => document.getElementById(id);
const KEY_STORE = "wca.keys";

const state = { all: [], messages: [], stats: null, title: "", mode: "wrapped", person: null, ai: { wrapped: null, profile: {} } };

// report styles live in report.js so the downloaded file and the page look identical
const style = document.createElement("style");
style.textContent = REPORT_CSS;
document.head.appendChild(style);

function showError(msg) {
  $("error").textContent = msg;
  $("error").hidden = !msg;
}

async function readFile(file) {
  const bytes = new Uint8Array(await file.arrayBuffer());
  return isZip(bytes) ? chatFromZip(bytes) : new TextDecoder("utf-8").decode(bytes);
}

function titleFrom(name) {
  return name.replace(/\.(zip|txt)$/i, "").replace(/^WhatsApp Chat (with |- )?/i, "").replace(/_/g, " ").trim() || "Chat";
}

function load(text, name) {
  const messages = parse(text);
  if (!messages.length) throw new Error("No messages found. Is this a WhatsApp export (Export chat → Without media)?");
  state.all = messages;
  state.title = titleFrom(name);
  state.ai = { wrapped: null, profile: {} };
  state.mode = "wrapped";
  $("period").value = "";
  $("start").hidden = true;
  $("app").hidden = false;
  update();
  scrollTo(0, 0);
}

async function handleFile(file) {
  if (!file) return;
  showError("");
  try {
    load(await readFile(file), file.name);
  } catch (e) {
    showError(e.message);
  }
}

function update() {
  state.messages = filterMessages(state.all, { last: $("period").value || null });
  if (!state.messages.length) {
    $("report").innerHTML = `<p class="note">No messages in this time window.</p>`;
    return;
  }
  state.stats = compute(state.messages);
  const people = state.stats.people;
  const select = $("person");
  select.innerHTML = "";
  for (const p of people) select.add(new Option(`${p.name} (${p.messages.toLocaleString("en-US")})`, p.name));
  if (!people.some((p) => p.name === state.person)) state.person = people[0].name;
  select.value = state.person;
  select.hidden = state.mode !== "profile";
  $("mode-wrapped").classList.toggle("on", state.mode === "wrapped");
  $("mode-profile").classList.toggle("on", state.mode === "profile");
  $("ai-go").textContent = state.mode === "wrapped" ? "Generate the AI recap" : `Describe how ${state.person} communicates`;
  render();
}

function render() {
  const s = state.stats;
  const person = state.mode === "profile" ? s.people.find((p) => p.name === state.person) : null;
  const opts = state.mode === "wrapped"
    ? { aiWrapped: state.ai.wrapped }
    : { person, aiProfile: state.ai.profile[state.person] || null };
  $("report").innerHTML = renderReport(s, reportTitle(), opts);
}

const reportTitle = () => (state.mode === "wrapped" ? `${state.title} · Wrapped` : `${state.person} · ${state.title}`);

function download() {
  const html = reportDocument($("report").innerHTML, reportTitle());
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([html], { type: "text/html" }));
  a.download = `${reportTitle().replace(/[^\p{L}\p{N} _-]+/gu, "").trim().replace(/\s+/g, "_")}.html`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

// ---- AI ----
function savedKeys() {
  try { return JSON.parse(localStorage.getItem(KEY_STORE)) || {}; } catch { return {}; }
}

function syncProvider() {
  const provider = $("provider").value;
  $("model").placeholder = DEFAULT_MODELS[provider];
  $("key").placeholder = provider === "claude" ? "sk-ant-…" : "sk-…";
  const saved = savedKeys()[provider];
  if (saved && !$("key").value) $("key").value = saved;
  $("remember").checked = !!saved;
}

function askConfirm() {
  if (!$("key").value.trim()) {
    $("ai-status").textContent = "Paste your API key first.";
    return;
  }
  const who = $("provider").value === "claude" ? "Anthropic" : "OpenAI";
  $("ai-confirm-text").textContent = `The most recent part of this chat (up to ~150,000 characters) will be sent to ${who}` +
    ($("anon").checked ? ", with names, phone numbers, emails and links hidden." : ", with real names included.");
  $("ai-confirm").hidden = false;
  $("ai-go").hidden = true;
  $("ai-status").textContent = "";
}

async function sendAI() {
  $("ai-confirm").hidden = true;
  $("ai-go").hidden = false;
  const provider = $("provider").value, key = $("key").value.trim();
  const keys = savedKeys();
  if ($("remember").checked) keys[provider] = key; else delete keys[provider];
  try { localStorage.setItem(KEY_STORE, JSON.stringify(keys)); } catch { /* storage blocked: key stays in memory */ }

  $("ai-go").disabled = true;
  $("ai-status").textContent = `Asking ${provider === "claude" ? "Claude" : "OpenAI"}… this can take a minute.`;
  const mode = state.mode, person = state.person;
  try {
    const result = await analyze(mode, state.stats, state.messages, {
      provider, key, model: $("model").value.trim() || null, anonymize: $("anon").checked,
      language: $("lang").value.trim(), person,
    });
    if (mode === "wrapped") state.ai.wrapped = result; else state.ai.profile[person] = result;
    $("ai-status").textContent = "Done. AI text is generated and may be wrong.";
    render();
    $("report").querySelector(".ai")?.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (e) {
    $("ai-status").textContent = `⚠ ${e.message}`;
  } finally {
    $("ai-go").disabled = false;
  }
}

// ---- tooltips (no inline scripts: the page's security policy forbids them) ----
const tip = $("tip");
document.addEventListener("mousemove", (e) => {
  const t = e.target.closest?.("[data-tip]");
  if (!t) { tip.style.opacity = 0; return; }
  tip.textContent = t.dataset.tip;
  tip.style.opacity = 1;
  tip.style.left = Math.min(e.clientX + 14, innerWidth - tip.offsetWidth - 8) + "px";
  tip.style.top = e.clientY + 14 + "px";
});
addEventListener("scroll", () => { tip.style.opacity = 0; }, { passive: true });

// ---- wiring ----
const drop = $("drop");
$("file").addEventListener("change", (e) => handleFile(e.target.files[0]));
drop.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); $("file").click(); } });
for (const ev of ["dragenter", "dragover"]) drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("over"); });
for (const ev of ["dragleave", "drop"]) drop.addEventListener(ev, () => drop.classList.remove("over"));
drop.addEventListener("drop", (e) => { e.preventDefault(); handleFile(e.dataTransfer.files[0]); });
addEventListener("dragover", (e) => e.preventDefault());          // dropping outside the box shouldn't open the file
addEventListener("drop", (e) => { if (!drop.contains(e.target)) e.preventDefault(); });

$("sample").addEventListener("click", async () => {
  showError("");
  try {
    const res = await fetch("sample_chat.txt");
    load(await res.text(), "Sample chat");
  } catch (e) { showError(`Couldn't load the sample: ${e.message}`); }
});
$("mode-wrapped").addEventListener("click", () => { state.mode = "wrapped"; update(); });
$("mode-profile").addEventListener("click", () => { state.mode = "profile"; update(); });
$("person").addEventListener("change", (e) => { state.person = e.target.value; update(); });
$("period").addEventListener("change", () => { state.ai = { wrapped: null, profile: {} }; update(); });
$("download").addEventListener("click", download);
$("reset").addEventListener("click", () => {
  Object.assign(state, { all: [], messages: [], stats: null });
  $("report").innerHTML = "";
  $("file").value = "";
  $("app").hidden = true;
  $("start").hidden = false;
});
$("provider").addEventListener("change", () => { $("key").value = ""; syncProvider(); });
$("ai-go").addEventListener("click", askConfirm);
$("ai-send").addEventListener("click", sendAI);
$("ai-cancel").addEventListener("click", () => { $("ai-confirm").hidden = true; $("ai-go").hidden = false; });
syncProvider();
