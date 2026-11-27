// Parse WhatsApp chat exports (iOS and Android, any date order). Mirrors wca/parser.py.

const INVISIBLE = /[‎‏﻿]/g;
const SPACES = /[  ]/g;
const DATE = String.raw`(\d{1,4})[/.\-](\d{1,2})[/.\-](\d{1,4})`;
const TIME = String.raw`(\d{1,2})[:.](\d{2})(?:[:.](\d{2}))?\s*([AaPp]\.?\s?[Mm]\.?)?`;
const IOS = new RegExp(String.raw`^\[${DATE},?\s+${TIME}\]\s+(.*)$`);
const ANDROID = new RegExp(String.raw`^${DATE},?\s+${TIME}\s+[-–]\s+(.*)$`);

const MEDIA_MARKERS = [
  "<media omitted>", "<media omessi>", "<media omesso>", "<multimedia omitido>",
  "image omitted", "video omitted", "audio omitted", "sticker omitted", "gif omitted",
  "document omitted", "contact card omitted",
  "immagine omessa", "video omesso", "audio omesso", "sticker omesso", "gif omessa",
  "documento omesso", "scheda contatto omessa", "<attached:", "<allegato:",
];
const DELETED_MARKERS = [
  "this message was deleted", "you deleted this message",
  "questo messaggio è stato eliminato", "hai eliminato questo messaggio",
];
const EDITED_MARKERS = ["<this message was edited>", "<questo messaggio è stato modificato>"];
const SYSTEM_MARKERS = [
  "end-to-end encrypted", "crittografati end-to-end", "crittografia end-to-end",
  "created group", "ha creato il gruppo", "added you", "ti ha aggiunto",
  "changed the subject", "ha cambiato l'oggetto", "changed this group's icon",
  "ha cambiato l'immagine di questo gruppo", "changed the group description",
  "joined using this group's invite link", "si è unito tramite il link",
  "security code changed", "codice di sicurezza", "is a contact", "è un contatto",
  "disappearing messages", "messaggi effimeri", "you're now an admin", "ora sei un amministratore",
];

function match(line) {
  for (const [re, android] of [[IOS, false], [ANDROID, true]]) {
    const m = re.exec(line);
    if (m) {
      const [, a, b, c, hh, mm, ss, ampm, body] = m;
      return { d: [+a, +b, +c], t: [+hh, +mm, +(ss || 0), ampm || null], body, android };
    }
  }
  return null;
}

export function detectDateOrder(raws) {
  if (raws.some((r) => r.d[0] > 31)) return "ymd";
  if (raws.some((r) => r.d[0] > 12)) return "dmy";
  if (raws.some((r) => r.d[1] > 12)) return "mdy";
  return "dmy";
}

function toDate(r, order) {
  const [a, b, c] = r.d;
  let [year, month, day] = { ymd: [a, b, c], dmy: [c, b, a], mdy: [c, a, b] }[order];
  if (year < 100) year += 2000;
  let [hh, mm, ss, ampm] = r.t;
  if (ampm) hh = (hh % 12) + (ampm.toLowerCase().startsWith("p") ? 12 : 0);
  const d = new Date(year, month - 1, day, hh, mm, ss);
  // reject impossible dates (e.g. 31/02), which Date would silently roll over
  if (d.getFullYear() !== year || d.getMonth() !== month - 1 || d.getDate() !== day) return null;
  return d;
}

function classify(text) {
  let low = text.toLowerCase().trim();
  for (const marker of EDITED_MARKERS) {
    if (low.endsWith(marker)) {
      text = text.slice(0, text.length - marker.length).trimEnd();
      low = text.toLowerCase().trim();
    }
  }
  if (MEDIA_MARKERS.some((m) => low.startsWith(m) || low === m) ||
      low.endsWith(" omitted") || low.endsWith(" omessa") || low.endsWith(" omesso")) {
    return ["media", ""];
  }
  if (DELETED_MARKERS.some((m) => low.includes(m)) && low.length < 60) return ["deleted", ""];
  return ["text", text];
}

/** Parse the full text of an export into [{ts: Date, sender, text, kind}]. */
export function parse(text, dateOrder = null) {
  const entries = [];
  for (const line of text.replace(INVISIBLE, "").replace(SPACES, " ").split(/\r?\n/)) {
    const raw = match(line);
    if (raw) entries.push([raw, [raw.body]]);
    else if (entries.length) entries[entries.length - 1][1].push(line); // multi-line message
  }
  const order = dateOrder || detectDateOrder(entries.map((e) => e[0]));
  const messages = [];
  for (const [raw, lines] of entries) {
    const body = lines.join("\n");
    const i = body.indexOf(": ");
    if (i < 0 || i > 60) continue; // system line with no sender
    const sender = body.slice(0, i).trim();
    const content = body.slice(i + 2);
    const low = content.toLowerCase();
    if (SYSTEM_MARKERS.some((m) => low.includes(m)) && content.length < 200) continue;
    const ts = toDate(raw, order);
    if (!ts) continue;
    const [kind, clean] = classify(content);
    messages.push({ ts, sender, text: clean.trim(), kind });
  }
  messages.sort((a, b) => a.ts - b.ts);
  return messages;
}
