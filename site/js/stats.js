// Everything we can say about a chat without AI. Mirrors wca/stats.py.

const CONVERSATION_GAP = 4 * 3600 * 1000;
const URL_RE = /https?:\/\/\S+|www\.\S+/gi;
const WORD_RE = /\p{L}{3,}/gu;
const LAUGH_RE = /(?<![\p{L}])(?:a?h[ae]h[ae]\p{L}*|(?:ha){2,}\p{L}*|(?:ah){2,}\p{L}*|lol+|lmao+|xd+)(?![\p{L}])/giu;
const PICTO = /\p{Extended_Pictographic}|\p{Regional_Indicator}/u;
const segmenter = new Intl.Segmenter(undefined, { granularity: "grapheme" });

const STOPWORDS = new Set(`
the and for are but not you all any can had her was one our out has him his how its may new now old see two way who
did get got let say she too use that with have this will your from they know want been good much some time very when
come here just like long make many more only over such take than them well were what where which while would there
their then these those about after again also because before being could doing does dont down each even every into
just more most other should since still thing think through under until yeah yes okay really going gonna its
che non per una del della delle dei degli con come anche sono sei ma più piu cosa questo questa quello quella ho hai
ha abbiamo avete hanno era ero eri sta sto stai fare fatto fai faccio ci si se mi ti lo la le li gli un uno nel nella
nei negli dal dalla alla allo alle agli sul sulla poi già gia ancora quando dove perché perche perchè quindi però pero
tutto tutti tutta tutte molto poco bene male oggi domani ieri adesso ora qui qua lì là così cosi solo sempre mai niente
nulla qualcosa tipo boh comunque magari anzi infatti oppure mentre dopo prima allora essere avere sia siamo siete sui
`.split(/\s+/).filter(Boolean));

export const dayKey = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const monthKey = (d) => dayKey(d).slice(0, 7);
const weekday = (d) => (d.getDay() + 6) % 7; // 0 = Monday

function countUp(map, key, n = 1) { map.set(key, (map.get(key) || 0) + n); }
function top(map, n) { return [...map.entries()].sort((a, b) => b[1] - a[1]).slice(0, n); }
function median(xs) {
  if (!xs.length) return null;
  const s = [...xs].sort((a, b) => a - b), m = s.length >> 1;
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

export function emojisIn(text) {
  const out = [];
  for (const { segment } of segmenter.segment(text)) if (PICTO.test(segment)) out.push(segment);
  return out;
}

export function fmtMinutes(m) {
  if (m == null) return "-";
  if (m < 1) return `${Math.round(m * 60)}s`;
  if (m < 90) return `${Math.round(m)} min`;
  return `${(m / 60).toFixed(1)} h`;
}

function newPerson(name) {
  return { name, messages: 0, words: 0, media: 0, links: 0, deleted: 0, emojis: 0, laughs: 0, questions: 0,
    conversationStarts: 0, nightMessages: 0, longestMessageWords: 0, replySeconds: [],
    emojiCount: new Map(), wordCount: new Map() };
}

function finishPerson(p, topN) {
  const texts = p.messages - p.media - p.deleted;
  p.avgWords = texts ? p.words / texts : 0;
  const med = median(p.replySeconds);
  p.medianReplyMinutes = med == null ? null : med / 60;
  p.nightPct = p.messages ? (100 * p.nightMessages) / p.messages : 0;
  p.emojisPerMessage = p.messages ? p.emojis / p.messages : 0;
  p.topEmojis = top(p.emojiCount, topN);
  p.topWords = top(p.wordCount, topN);
  return p;
}

function awards(people) {
  if (people.length < 2) return [];
  const out = [];
  const active = (p) => p.messages >= 20;
  const give = (title, emoji, key, fmt, eligible = () => true, highest = true) => {
    const pool = people.filter((p) => eligible(p) && key(p) != null);
    if (!pool.length) return;
    const w = [...pool].sort((a, b) => (highest ? key(b) - key(a) : key(a) - key(b)))[0];
    if (highest && !key(w)) return;
    out.push({ title, emoji, winner: w.name, detail: fmt(w) });
  };
  give("Chatterbox", "💬", (p) => p.messages, (p) => `${p.messages.toLocaleString()} messages`);
  give("Novelist", "📜", (p) => p.avgWords, (p) => `${p.avgWords.toFixed(1)} words per message`, active);
  give("Speed Demon", "⚡", (p) => p.medianReplyMinutes, (p) => `replies in ~${fmtMinutes(p.medianReplyMinutes)}`,
    (p) => p.replySeconds.length >= 10, false);
  give("Ice Breaker", "🧊", (p) => p.conversationStarts, (p) => `started ${p.conversationStarts} conversations`);
  give("Night Owl", "🦉", (p) => p.nightPct, (p) => `${p.nightPct.toFixed(0)}% of messages between 0:00 and 5:00`, active);
  give("Emoji Royalty", "👑", (p) => p.emojisPerMessage, (p) => `${p.emojisPerMessage.toFixed(2)} emojis per message`, active);
  give("Comedian", "😂", (p) => p.laughs, (p) => `${p.laughs} laughs (haha, lol, 😂...)`);
  give("Curious Mind", "❓", (p) => p.questions, (p) => `asked ${p.questions} questions`);
  give("Photographer", "📸", (p) => p.media, (p) => `${p.media} photos, videos and stickers`);
  return out;
}

export function compute(messages, topN = 10) {
  if (!messages.length) throw new Error("No messages to analyze");
  const people = new Map();
  const heatmap = Array.from({ length: 7 }, () => Array(24).fill(0));
  const monthly = new Map();
  const perDay = new Map();
  const allEmojis = new Map(), allWords = new Map();
  let conversations = 0;
  let silence = { ms: 0, from: messages[0].ts, to: messages[0].ts };
  let prev = null;

  for (const m of messages) {
    if (!people.has(m.sender)) people.set(m.sender, newPerson(m.sender));
    const p = people.get(m.sender);
    p.messages++;
    heatmap[weekday(m.ts)][m.ts.getHours()]++;
    const mk = monthKey(m.ts);
    if (!monthly.has(mk)) monthly.set(mk, new Map());
    countUp(monthly.get(mk), m.sender);
    countUp(perDay, dayKey(m.ts));
    if (m.ts.getHours() < 5) p.nightMessages++;

    const gap = prev ? m.ts - prev.ts : null;
    if (prev === null || gap > CONVERSATION_GAP) { conversations++; p.conversationStarts++; }
    else if (m.sender !== prev.sender) p.replySeconds.push(gap / 1000);
    if (gap && gap > silence.ms) silence = { ms: gap, from: prev.ts, to: m.ts };
    prev = m;

    if (m.kind === "media") { p.media++; continue; }
    if (m.kind === "deleted") { p.deleted++; continue; }
    const nWords = m.text.split(/\s+/).filter(Boolean).length;
    p.words += nWords;
    p.longestMessageWords = Math.max(p.longestMessageWords, nWords);
    p.links += (m.text.match(URL_RE) || []).length;
    const found = emojisIn(m.text);
    p.emojis += found.length;
    for (const e of found) { countUp(p.emojiCount, e); countUp(allEmojis, e); }
    p.laughs += (m.text.match(LAUGH_RE) || []).length + found.filter((e) => ["😂", "🤣", "😆"].includes(e)).length;
    if (m.text.includes("?")) p.questions++;
    for (const w of m.text.replace(URL_RE, " ").toLowerCase().match(WORD_RE) || []) {
      if (!STOPWORDS.has(w)) { countUp(p.wordCount, w); countUp(allWords, w); }
    }
  }

  const ranked = [...people.values()].map((p) => finishPerson(p, topN)).sort((a, b) => b.messages - a.messages);
  const days = [...perDay.keys()].sort();
  // longest run of consecutive days with messages
  let streak = { days: 1, from: days[0], to: days[0] }, start = days[0];
  for (let i = 1; i < days.length; i++) {
    const diff = (new Date(days[i]) - new Date(days[i - 1])) / 86400000;
    if (Math.round(diff) !== 1) start = days[i];
    const len = Math.round((new Date(days[i]) - new Date(start)) / 86400000) + 1;
    if (len > streak.days) streak = { days: len, from: start, to: days[i] };
  }
  const busiest = [...perDay.entries()].sort((a, b) => b[1] - a[1])[0];
  const first = messages[0].ts, last = messages[messages.length - 1].ts;
  const spanDays = Math.round((new Date(dayKey(last)) - new Date(dayKey(first))) / 86400000) + 1;

  return {
    people: ranked,
    totalMessages: messages.length,
    totalWords: ranked.reduce((s, p) => s + p.words, 0),
    first, last, spanDays,
    activeDays: days.length,
    conversations,
    busiestDay: { date: busiest[0], messages: busiest[1] },
    longestStreak: streak,
    longestSilence: silence,
    heatmap,
    monthly: new Map([...monthly.entries()].sort()),
    topEmojis: top(allEmojis, topN),
    topWords: top(allWords, topN),
    awards: awards(ranked),
  };
}

const PERIOD = { d: 1, w: 7, m: 30, y: 365 };

/** Keep a time window. `last` ("3w", "6m"...) counts back from the chat's last message. */
export function filterMessages(messages, { since = null, until = null, last = null } = {}) {
  if (last && messages.length) {
    const m = /^(\d+)([dwmy])$/.exec(last);
    if (!m) throw new Error(`Invalid period '${last}'`);
    const from = new Date(messages[messages.length - 1].ts - +m[1] * PERIOD[m[2]] * 86400000);
    since = since && since > from ? since : from;
  }
  return messages.filter((m) => (!since || m.ts >= since) && (!until || m.ts <= until));
}

/** A JSON-friendly summary for the AI prompt and for download. */
export function toJSON(s) {
  return {
    people: s.people.map(({ emojiCount, wordCount, replySeconds, ...p }) => ({
      ...p, avgWords: +p.avgWords.toFixed(2), nightPct: +p.nightPct.toFixed(1),
      emojisPerMessage: +p.emojisPerMessage.toFixed(3), replies: replySeconds.length })),
    totalMessages: s.totalMessages, totalWords: s.totalWords,
    first: s.first.toISOString(), last: s.last.toISOString(), spanDays: s.spanDays,
    activeDays: s.activeDays, conversations: s.conversations, busiestDay: s.busiestDay,
    longestStreak: s.longestStreak,
    longestSilenceDays: +(s.longestSilence.ms / 86400000).toFixed(1),
    topEmojis: s.topEmojis, topWords: s.topWords, awards: s.awards,
  };
}
