// Optional AI, with the visitor's own API key, called straight from the browser. Mirrors wca/ai.py.

import { toJSON } from "./stats.js";

export const DEFAULT_MODELS = { claude: "claude-opus-5-5", openai: "gpt-4.1-mini" };

const PHONE = /(?<![\w-])\+?\d(?:[ \-]?\d){8,14}(?![\w-])/g;
const EMAIL = /[\w.+-]+@[\w-]+\.[\w.]+/g;
const URL_RE = /https?:\/\/\S+|www\.\S+/gi;

const GROUND_RULES = `Ground rules:
- Base every statement on the transcript or the stats. If something can't be inferred, say so.
- Describe how people communicate, not who they are: no diagnoses, no personality disorders, no mental-health,
  health, sexuality, religion or other sensitive speculation, no judgments of character.
- Be warm and playful, never mocking. Write as if every participant will read it.
- Quote sparingly (a few words at most) and never quote anything that looks private or sensitive.
`;
const WRAPPED_SYSTEM = "You write the 'Wrapped' recap of a WhatsApp chat: a fun, warm end-of-year style summary " +
  "that the people in the chat will enjoy reading together.\n" + GROUND_RULES;
const PROFILE_SYSTEM = "You describe one person's communication style in a WhatsApp chat, to help others " +
  "understand how they communicate. It is not a psychological assessment.\n" + GROUND_RULES;

const item = (props) => ({ type: "object", properties: props, required: Object.keys(props), additionalProperties: false });
const str = { type: "string" };
const WRAPPED_SCHEMA = item({
  vibe: { type: "string", description: "One sentence capturing the vibe of this chat." },
  topics: { type: "array", description: "3-6 recurring topics or running jokes.", items: item({ title: str, description: str }) },
  moments: { type: "array", description: "3-5 memorable moments, with their date.", items: item({ date: str, description: str }) },
  people: { type: "array", description: "How each participant shows up in the chat (max 8).", items: item({ name: str, description: str }) },
  closing: { type: "string", description: "A short, warm closing line." },
});
const PROFILE_SCHEMA = item({
  summary: { type: "string", description: "2-3 sentences on how this person communicates." },
  sections: { type: "array", description: "Writing style; tone and humor; how they engage; topics they bring; what they bring to the chat.",
    items: item({ title: str, points: { type: "array", items: str } }) },
  tips: { type: "array", description: "3-5 tips for chatting well with this person.", items: str },
  confidence: { type: "string", description: "How much data this is based on and what it can't tell." },
});

const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

export class Aliases {
  constructor(names) {
    const letter = (i) => (i < 26 ? String.fromCharCode(65 + i) : String.fromCharCode(65 + Math.floor(i / 26) - 1) + String.fromCharCode(65 + (i % 26)));
    this.forward = new Map(names.map((n, i) => [n, `Person ${letter(i)}`]));
  }
  hideNames(text) {
    const byLength = [...this.forward.entries()].sort((a, b) => b[0].length - a[0].length);
    for (const [real, alias] of byLength) {
      text = text.replace(new RegExp(`(?<![\\p{L}\\p{N}_])${escapeRe(real)}(?![\\p{L}\\p{N}_])`, "giu"), alias);
    }
    const firsts = new Map();
    for (const real of this.forward.keys()) {
      const first = real.split(/\s+/)[0];
      if (first.length >= 3) firsts.set(first, [...(firsts.get(first) || []), real]);
    }
    for (const [first, reals] of firsts) {
      if (reals.length === 1) {
        text = text.replace(new RegExp(`(?<![\\p{L}\\p{N}_])${escapeRe(first)}(?![\\p{L}\\p{N}_])`, "giu"), this.forward.get(reals[0]));
      }
    }
    return text;
  }
  hide(text) {
    return this.hideNames(text.replace(PHONE, "[phone]").replace(EMAIL, "[email]").replace(URL_RE, "[link]"));
  }
  reveal(value) {
    if (typeof value === "string") {
      for (const [real, alias] of [...this.forward.entries()].sort((a, b) => b[1].length - a[1].length)) {
        value = value.split(alias).join(real);
      }
      return value;
    }
    if (Array.isArray(value)) return value.map((v) => this.reveal(v));
    if (value && typeof value === "object") return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, this.reveal(v)]));
    return value;
  }
}

const pad = (n) => String(n).padStart(2, "0");
const stamp = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;

/** Most recent messages that fit the budget, oldest first. */
export function transcript(messages, budget, aliases) {
  const lines = [];
  let used = 0;
  for (let i = messages.length - 1; i >= 0; i--) {
    const m = messages[i];
    let body = m.kind === "media" ? "<media>" : m.kind === "deleted" ? "<deleted>" : m.text;
    if (aliases) body = aliases.hide(body);
    const sender = aliases ? aliases.forward.get(m.sender) : m.sender;
    const line = `${stamp(m.ts)} | ${sender}: ${body}`;
    if (used + line.length > budget && lines.length) break;
    lines.push(line);
    used += line.length + 1;
  }
  return { text: lines.reverse().join("\n"), included: lines.length };
}

function buildPrompt(task, stats, messages, { budget, aliases, language }) {
  const { text, included } = transcript(messages, budget, aliases);
  const note = included === messages.length ? "" :
    `(Only the most recent ${included.toLocaleString()} of ${messages.length.toLocaleString()} messages fit; the stats cover all of them.)\n`;
  const lang = language ? `Write in ${language}.` :
    "Write in the language most messages are written in (judge from the message text, not from names).";
  let brief = JSON.stringify(toJSON(stats));
  if (aliases) brief = aliases.hideNames(brief);
  return `${task}\n${lang}\n\n<stats>\n${brief}\n</stats>\n\n<transcript>\n${note}${text}\n</transcript>`;
}

async function callClaude({ key, model, system, prompt, schema, effort }) {
  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-api-key": key,
      "anthropic-version": "2026-10-21",
      "anthropic-beta": "server-side-fallback-2026-07-01",
      // The key belongs to the visitor and never leaves their browser except to Anthropic.
      "anthropic-dangerous-direct-browser-access": "true",
    },
    body: JSON.stringify({
      model, max_tokens: 16000, system,
      messages: [{ role: "user", content: prompt }],
      output_config: { effort, format: { type: "json_schema", schema } },
      fallbacks: "default",
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = data?.error?.message || res.statusText;
    if (res.status === 401) throw new Error("Claude: the API key is not valid");
    if (res.status === 429) throw new Error("Claude: rate limited, try again in a minute");
    throw new Error(`Claude API error ${res.status}: ${msg}`);
  }
  if (data.stop_reason === "refusal") throw new Error("Claude declined to analyze this chat");
  if (data.stop_reason === "max_tokens") throw new Error("Claude's answer was cut off; lower the amount of chat sent");
  const text = (data.content || []).find((b) => b.type === "text")?.text || "";
  return JSON.parse(text);
}

async function callOpenAI({ key, model, system, prompt, schema, name }) {
  const res = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: { "content-type": "application/json", authorization: `Bearer ${key}` },
    body: JSON.stringify({
      model,
      messages: [{ role: "system", content: system }, { role: "user", content: prompt }],
      response_format: { type: "json_schema", json_schema: { name, schema, strict: true } },
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (res.status === 401) throw new Error("OpenAI: the API key is not valid");
    throw new Error(`OpenAI API error ${res.status}: ${data?.error?.message || res.statusText}`);
  }
  const msg = data.choices?.[0]?.message;
  if (msg?.refusal) throw new Error(`OpenAI declined: ${msg.refusal}`);
  return JSON.parse(msg?.content || "{}");
}

async function run(opts) {
  const model = opts.model || DEFAULT_MODELS[opts.provider];
  try {
    return opts.provider === "claude" ? await callClaude({ ...opts, model }) : await callOpenAI({ ...opts, model });
  } catch (e) {
    if (e instanceof TypeError) throw new Error(`Couldn't reach ${opts.provider === "claude" ? "Anthropic" : "OpenAI"} (network or browser blocked the request)`);
    throw e;
  }
}

/** mode: "wrapped" | "profile". Returns the parsed JSON, with real names restored. */
export async function analyze(mode, stats, messages, { provider, key, model, budget = 150000, anonymize = true,
  language = "", effort = "medium", person = null }) {
  const aliases = anonymize ? new Aliases(stats.people.map((p) => p.name)) : null;
  const who = aliases && person ? aliases.forward.get(person) : person;
  const task = mode === "wrapped" ? "Write the Wrapped recap of this chat." :
    `Describe the communication style of ${who}. Use the other participants' messages only as context for how ${who} interacts.`;
  const prompt = buildPrompt(task, stats, messages, { budget, aliases, language });
  const result = await run({
    provider, key, model, prompt, effort,
    system: mode === "wrapped" ? WRAPPED_SYSTEM : PROFILE_SYSTEM,
    schema: mode === "wrapped" ? WRAPPED_SCHEMA : PROFILE_SCHEMA,
    name: mode === "wrapped" ? "chat_wrapped" : "communication_profile",
  });
  return aliases ? aliases.reveal(result) : result;
}
