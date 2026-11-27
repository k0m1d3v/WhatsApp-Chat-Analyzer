// The report: inline SVG charts, light and dark mode. Mirrors wca/report.py.

import { fmtMinutes } from "./stats.js";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const N_SERIES = 7; // people beyond this fold into "Others"
const HEAT_STEPS = 7;

export const REPORT_CSS = `
.report { color-scheme: light;
  --page:#f9f9f9; --surface:#ffffff; --ink:#191919; --ink-2:#666666; --grid:#e7e7e7; --axis:#c2c2c2;
  --ring:rgba(11,11,11,.10); --empty:#f1f1f1;
  --s1:#257de0; --s2:#f47230; --s3:#00b894; --s4:#f2a600; --s5:#ee7fac; --s6:#008a17; --s7:#6a4ce2; --s8:#9c9c9c;
  --h0:#cce3fd; --h1:#9dc8f7; --h2:#6aabf1; --h3:#338ced; --h4:#2370cd; --h5:#1757ac; --h6:#0e3d7e;
  color: var(--ink); }
@media (prefers-color-scheme: dark) { .report { color-scheme: dark;
  --page:#0b0b0b; --surface:#191919; --ink:#efefef; --ink-2:#9c9c9c; --grid:#303030; --axis:#474747;
  --ring:rgba(255,255,255,.10); --empty:#222222;
  --s1:#338ced; --s2:#e76624; --s3:#00a888; --s4:#d28e05; --s5:#e24d8b; --s6:#0aac23; --s7:#9887ef; --s8:#5e5e5e;
  --h0:#0e3d7e; --h1:#1757ac; --h2:#2370cd; --h3:#338ced; --h4:#6aabf1; --h5:#9dc8f7; --h6:#cce3fd; } }
.report header h1 { font-size: 40px; line-height:1.1; margin: 0 0 6px; letter-spacing:-.02em; }
.report header p { color: var(--ink-2); margin: 0; }
.report section { background: var(--surface); border-radius: 16px; box-shadow: 0 0 0 1px var(--ring); padding: 24px; margin-top: 20px; }
.report h2 { font-size: 18px; margin: 0 0 4px; }
.report .sub { color: var(--ink-2); margin: 0 0 16px; font-size: 14px; }
.report .tiles { display:grid; grid-template-columns: repeat(auto-fill, minmax(150px,1fr)); gap: 12px; margin-top: 28px; }
.report .tile { background: var(--surface); border-radius: 14px; box-shadow: 0 0 0 1px var(--ring); padding: 16px 18px; }
.report .tile b { display:block; font-size: 28px; line-height:1.15; }
.report .tile span { color: var(--ink-2); font-size: 13px; }
.report .grid2 { display:grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 20px; }
.report .grid2 > section { margin-top: 0; }
@media (max-width: 760px) { .report .grid2 { grid-template-columns: 1fr; } }
.report .awards { display:grid; grid-template-columns: repeat(auto-fill, minmax(200px,1fr)); gap: 12px; }
.report .award { border-radius: 12px; box-shadow: 0 0 0 1px var(--ring); padding: 14px 16px; }
.report .award .e { font-size: 26px; } .report .award b { display:block; } .report .award span { color: var(--ink-2); font-size: 13px; }
.report .table-wrap { overflow-x: auto; }
.report table { border-collapse: collapse; width: 100%; font-variant-numeric: tabular-nums; }
.report th, .report td { text-align: right; padding: 7px 10px; border-bottom: 1px solid var(--grid); white-space: nowrap; }
.report th:first-child, .report td:first-child { text-align: left; }
.report th { color: var(--ink-2); font-weight: 500; font-size: 13px; }
.report .swatch { display:inline-block; width:10px; height:10px; border-radius:3px; margin-right:8px; }
.report .legend { display:flex; flex-wrap:wrap; gap: 4px 16px; color: var(--ink-2); font-size: 13px; margin-bottom: 8px; }
.report ol.rank { margin:0; padding:0; list-style:none; }
.report ol.rank li { display:flex; justify-content:space-between; padding: 6px 0; border-bottom: 1px solid var(--grid); }
.report ol.rank li span:last-child { color: var(--ink-2); font-variant-numeric: tabular-nums; }
.report .emoji li span:first-child { font-size: 20px; }
.report svg { display:block; width:100%; height:auto; overflow: visible; }
.report svg text { fill: var(--ink-2); font-size: 12px; font-family: inherit; }
.report svg .grid { stroke: var(--grid); stroke-width: 1; } .report svg .axis { stroke: var(--axis); stroke-width: 1; }
.report svg [data-tip]:hover { opacity: .8; }
.report .ai p { margin: 0 0 12px; } .report .ai h3 { font-size: 15px; margin: 18px 0 6px; }
.report .ai ul { margin: 0; padding-left: 20px; } .report .ai li { margin: 4px 0; }
.report .vibe { font-size: 20px; font-weight: 600; }
.report .note { color: var(--ink-2); font-size: 13px; }
.report footer { color: var(--ink-2); font-size: 13px; margin-top: 32px; text-align: center; }
#tip { position: fixed; pointer-events: none; background: #191919; color: #fff; padding: 6px 10px;
  border-radius: 8px; font-size: 13px; opacity: 0; transition: opacity .1s; white-space: pre; z-index: 9; }
`;

export const TOOLTIP_JS = `
(() => { const tip = document.getElementById('tip');
document.addEventListener('mousemove', e => {
  const t = e.target.closest && e.target.closest('[data-tip]');
  if (!t) { tip.style.opacity = 0; return; }
  tip.textContent = t.dataset.tip; tip.style.opacity = 1;
  tip.style.left = Math.min(e.clientX + 14, innerWidth - tip.offsetWidth - 8) + 'px'; tip.style.top = (e.clientY + 14) + 'px';
});
addEventListener('scroll', () => { tip.style.opacity = 0; }, {passive: true}); })();
`;

const esc = (x) => String(x).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const n = (x) => Number(x).toLocaleString("en-US");
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const LONG_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const LONG_DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const fmtDate = (d) => `${String(d.getDate()).padStart(2, "0")} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
const fromKey = (k) => { const [y, m, d] = k.split("-").map(Number); return new Date(y, m - 1, d || 1); };
const short = (s, max) => (s.length <= max ? s : s.slice(0, max - 1) + "…");

function niceTicks(peak, count = 4) {
  if (peak <= 0) return [0, 1];
  const raw = peak / count, mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((s) => s * mag).find((s) => s >= raw);
  return Array.from({ length: Math.ceil(peak / step) + 1 }, (_, i) => i * step);
}
const fmtTick = (v) => (v >= 10000 ? `${v / 1000}K` : n(v));

function colors(people) {
  return new Map(people.map((p, i) => [p.name, i < N_SERIES ? `var(--s${i + 1})` : "var(--s8)"]));
}

function hbar(rows, unitFmt = n, width = 400) {
  const labelW = 110, rowH = 30, barH = 18, valueW = 60, plotW = width - labelW - valueW;
  const peak = Math.max(...rows.map((r) => r[1]), 1);
  const out = [`<svg viewBox="0 0 ${width} ${rowH * rows.length}" role="img">`];
  rows.forEach(([label, v, color, tip], i) => {
    const y = i * rowH + (rowH - barH) / 2, w = Math.max(2, (plotW * v) / peak), r = Math.min(4, w / 2), x0 = labelW;
    const path = `M${x0},${y} H${x0 + w - r} Q${x0 + w},${y} ${x0 + w},${y + r} V${y + barH - r} Q${x0 + w},${y + barH} ${x0 + w - r},${y + barH} H${x0} Z`;
    out.push(`<text x="${labelW - 10}" y="${y + barH / 2 + 4}" text-anchor="end" style="fill:var(--ink)">${esc(short(label, 16))}</text>`);
    out.push(`<path d="${path}" style="fill:${color}" data-tip="${esc(tip)}"/>`);
    out.push(`<text x="${x0 + w + 8}" y="${y + barH / 2 + 4}">${esc(unitFmt(v))}</text>`);
  });
  out.push("</svg>");
  return out.join("");
}

function heatmap(s) {
  const cell = 30, gap = 2, left = 40, top = 22, width = left + 24 * cell, height = top + 7 * cell;
  const peak = Math.max(...s.heatmap.flat(), 1);
  const out = [`<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Messages by weekday and hour">`];
  for (let h = 0; h < 24; h += 3) out.push(`<text x="${left + h * cell + cell / 2}" y="14" text-anchor="middle">${h}:00</text>`);
  s.heatmap.forEach((row, d) => {
    const y = top + d * cell;
    out.push(`<text x="${left - 8}" y="${y + cell / 2 + 4}" text-anchor="end">${DAYS[d]}</text>`);
    row.forEach((v, h) => {
      const fill = v ? `var(--h${Math.min(HEAT_STEPS - 1, Math.floor((HEAT_STEPS * v) / (peak + 1)))})` : "var(--empty)";
      const hh = String(h).padStart(2, "0");
      out.push(`<rect x="${left + h * cell + gap / 2}" y="${y + gap / 2}" width="${cell - gap}" height="${cell - gap}" rx="4" ` +
        `style="fill:${fill}" data-tip="${esc(`${DAYS[d]} ${hh}:00–${hh}:59\n${n(v)} messages`)}"/>`);
    });
  });
  out.push("</svg>");
  return out.join("");
}

function timeline(s, col) {
  const months = [...s.monthly.keys()];
  const series = s.people.length <= 4
    ? s.people.map((p) => [p.name, months.map((m) => s.monthly.get(m).get(p.name) || 0), col.get(p.name)])
    : [["All messages", months.map((m) => [...s.monthly.get(m).values()].reduce((a, b) => a + b, 0)), "var(--s1)"]];
  const width = 900, height = 260, left = 48, right = 110, top = 12, bottom = 28;
  const pw = width - left - right, ph = height - top - bottom;
  const ticks = niceTicks(Math.max(...series.flatMap(([, v]) => v)));
  const ymax = ticks[ticks.length - 1] || 1;
  const x = (i) => (months.length === 1 ? left + pw / 2 : left + (pw * i) / (months.length - 1));
  const y = (v) => top + ph - (ph * v) / ymax;
  const out = [`<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Messages per month">`];
  for (const t of ticks) {
    out.push(`<line class="${t === 0 ? "axis" : "grid"}" x1="${left}" x2="${left + pw}" y1="${y(t)}" y2="${y(t)}"/>`);
    out.push(`<text x="${left - 8}" y="${y(t) + 4}" text-anchor="end">${fmtTick(t)}</text>`);
  }
  const every = Math.max(1, Math.ceil(months.length / 10));
  months.forEach((m, i) => {
    if (i % every === 0) {
      const d = fromKey(m);
      out.push(`<text x="${x(i)}" y="${height - 8}" text-anchor="middle">${MONTHS[d.getMonth()]} ${String(d.getFullYear()).slice(2)}</text>`);
    }
  });
  const ends = series.map(([, v]) => y(v[v.length - 1])).sort((a, b) => a - b);
  const endLabels = ends.every((e, i) => i === 0 || e - ends[i - 1] >= 16); // colliding labels: the legend carries identity
  for (const [name, values, color] of series) {
    const pts = values.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
    const last = values.length - 1;
    if (series.length === 1) {
      out.push(`<polygon points="${x(0).toFixed(1)},${y(0)} ${pts} ${x(last).toFixed(1)},${y(0)}" style="fill:${color};opacity:.1"/>`);
    }
    out.push(`<polyline points="${pts}" fill="none" style="stroke:${color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>`);
    out.push(`<circle cx="${x(last)}" cy="${y(values[last])}" r="4" style="fill:${color};stroke:var(--surface)" stroke-width="2"/>`);
    if (endLabels) out.push(`<text x="${x(last) + 10}" y="${y(values[last]) + 4}" style="fill:var(--ink)">${esc(short(name, 14))}</text>`);
  }
  const colW = months.length > 1 ? pw / (months.length - 1) : pw;
  months.forEach((m, i) => {
    const d = fromKey(m);
    const tip = `${LONG_MONTHS[d.getMonth()]} ${d.getFullYear()}` + series.map(([nm, v]) => `\n${nm}: ${n(v[i])}`).join("");
    out.push(`<rect x="${x(i) - colW / 2}" y="${top}" width="${colW}" height="${ph}" fill="transparent" data-tip="${esc(tip)}"/>`);
  });
  out.push("</svg>");
  const legend = series.length > 1
    ? `<div class="legend">${series.map(([nm, , c]) => `<span><i class="swatch" style="background:${c}"></i>${esc(nm)}</span>`).join("")}</div>`
    : "";
  return legend + out.join("");
}

const rankList = (items, cls = "") => (items.length
  ? `<ol class="rank ${cls}">${items.map(([k, v]) => `<li><span>${esc(k)}</span><span>${n(v)}</span></li>`).join("")}</ol>`
  : `<p class="note">Nothing here.</p>`);

const tiles = (items) => `<div class="tiles">${items.map(([v, k]) => `<div class="tile"><b>${esc(v)}</b><span>${esc(k)}</span></div>`).join("")}</div>`;

function peopleTable(s, col) {
  const rows = s.people.map((p) => `<tr><td><i class="swatch" style="background:${col.get(p.name)}"></i>${esc(p.name)}</td>` +
    `<td>${n(p.messages)}</td><td>${Math.round((100 * p.messages) / s.totalMessages)}%</td><td>${p.avgWords.toFixed(1)}</td>` +
    `<td>${esc(fmtMinutes(p.medianReplyMinutes))}</td><td>${n(p.conversationStarts)}</td><td>${n(p.media)}</td>` +
    `<td>${n(p.emojis)}</td><td>${Math.round(p.nightPct)}%</td></tr>`).join("");
  return `<div class="table-wrap"><table><thead><tr><th>Name</th><th>Messages</th><th>Share</th><th>Words/msg</th><th>Reply time</th>` +
    `<th>Starts</th><th>Media</th><th>Emojis</th><th>Night</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

function aiWrapped(r) {
  const li = (items) => `<ul>${items.join("")}</ul>`;
  return `<section class="ai"><h2>✨ AI recap</h2><p class="vibe">${esc(r.vibe)}</p>` +
    `<h3>Topics &amp; running jokes</h3>${li(r.topics.map((t) => `<li><b>${esc(t.title)}</b> — ${esc(t.description)}</li>`))}` +
    `<h3>Memorable moments</h3>${li(r.moments.map((m) => `<li><b>${esc(m.date)}</b> — ${esc(m.description)}</li>`))}` +
    `<h3>Who's who</h3>${li(r.people.map((p) => `<li><b>${esc(p.name)}</b> — ${esc(p.description)}</li>`))}` +
    `<p style="margin-top:16px"><i>${esc(r.closing)}</i></p></section>`;
}

function aiProfile(name, r) {
  return `<section class="ai"><h2>✨ How ${esc(name)} communicates</h2><p class="vibe">${esc(r.summary)}</p>` +
    r.sections.map((sec) => `<h3>${esc(sec.title)}</h3><ul>${sec.points.map((p) => `<li>${esc(p)}</li>`).join("")}</ul>`).join("") +
    `<h3>Tips</h3><ul>${r.tips.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>` +
    `<p class="note" style="margin-top:16px">${esc(r.confidence)}</p></section>`;
}

/** The report body (no <html> wrapper). */
export function renderReport(s, title, { aiWrapped: aw = null, person = null, aiProfile: ap = null } = {}) {
  const col = colors(s.people);
  const shown = s.people.slice(0, N_SERIES), others = s.people.slice(N_SERIES);
  const barRows = shown.map((p) => [p.name, p.messages, col.get(p.name), `${p.name}\n${n(p.messages)} messages`]);
  if (others.length) {
    const total = others.reduce((a, p) => a + p.messages, 0);
    barRows.push([`Others (${others.length})`, total, "var(--s8)", `${others.length} more people\n${n(total)} messages`]);
  }
  const replyRows = shown.filter((p) => p.medianReplyMinutes != null)
    .sort((a, b) => a.medianReplyMinutes - b.medianReplyMinutes)
    .map((p) => [p.name, p.medianReplyMinutes, col.get(p.name),
      `${p.name}\ntypical reply: ${fmtMinutes(p.medianReplyMinutes)}\n(${n(p.replySeconds.length)} replies)`]);
  const streak = s.longestStreak, gapDays = Math.floor(s.longestSilence.ms / 86400000);
  const busy = fromKey(s.busiestDay.date);
  const pct = (p) => Math.round((100 * p.messages) / s.totalMessages);

  const body = [`<header><h1>${esc(title)}</h1><p>${fmtDate(s.first)} → ${fmtDate(s.last)} · ${s.people.length} people</p></header>`];
  body.push(tiles([
    [n(s.totalMessages), "messages"], [n(s.totalWords), "words"],
    [`${s.activeDays}/${s.spanDays}`, "days with messages"], [n(s.conversations), "conversations"],
    [`${streak.days} days`, `streak · ${fmtDate(fromKey(streak.from))} → ${fmtDate(fromKey(streak.to))}`],
    [gapDays ? `${gapDays} days` : `${Math.floor(s.longestSilence.ms / 3600000)} h`, `longest silence · from ${fmtDate(s.longestSilence.from)}`],
  ]));
  if (person) {
    body.push(`<section><h2>${esc(person.name)}</h2><p class="sub">Their numbers in this chat</p>` + tiles([
      [n(person.messages), `messages · ${pct(person)}% of the chat`],
      [person.avgWords.toFixed(1), "words per message"],
      [fmtMinutes(person.medianReplyMinutes), "typical reply time"],
      [n(person.conversationStarts), "conversations started"],
      [`${Math.round(person.nightPct)}%`, "messages 0:00–5:00"],
      [person.emojisPerMessage.toFixed(2), "emojis per message"],
    ]) + `<div class="grid2"><div><h2>Their emojis</h2>${rankList(person.topEmojis, "emoji")}</div>` +
      `<div><h2>Their words</h2>${rankList(person.topWords)}</div></div></section>`);
    if (ap) body.push(aiProfile(person.name, ap));
  }
  if (aw) body.push(aiWrapped(aw));
  if (s.awards.length) {
    body.push(`<section><h2>Awards</h2><p class="sub">Who wins what</p><div class="awards">` +
      s.awards.map((a) => `<div class="award"><div class="e">${esc(a.emoji)}</div><b>${esc(a.title)}</b>${esc(a.winner)}` +
        `<br><span>${esc(a.detail)}</span></div>`).join("") + "</div></section>");
  }
  body.push(`<div class="grid2"><section><h2>Who talks the most</h2><p class="sub">Messages per person</p>${hbar(barRows)}</section>`);
  if (replyRows.length) {
    body.push(`<section><h2>Who replies fastest</h2><p class="sub">Typical (median) time to reply, within a conversation</p>` +
      `${hbar(replyRows, fmtMinutes)}</section>`);
  }
  body.push("</div>");
  body.push(`<section><h2>When you chat</h2><p class="sub">Messages by weekday and hour · busiest day: ` +
    `${LONG_DAYS[busy.getDay()]} ${fmtDate(busy)} (${n(s.busiestDay.messages)} messages)</p>${heatmap(s)}</section>`);
  body.push(`<section><h2>Over time</h2><p class="sub">Messages per month</p>${timeline(s, col)}</section>`);
  body.push(`<div class="grid2"><section><h2>Top emojis</h2>${rankList(s.topEmojis, "emoji")}</section>` +
    `<section><h2>Top words</h2>${rankList(s.topWords)}</section></div>`);
  body.push(`<section><h2>Everyone</h2><p class="sub">The full numbers</p>${peopleTable(s, col)}</section>`);
  body.push(`<footer>Made with WhatsApp Chat Analyzer · ${fmtDate(new Date())}` +
    (aw || ap ? " · AI text is generated and may be wrong" : "") + "</footer>");
  return body.join("");
}

/** A standalone HTML file of the report, same as the CLI's. */
export function reportDocument(bodyHtml, title) {
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">` +
    `<title>${esc(title)}</title><style>*{box-sizing:border-box}body{margin:0;background:#f9f9f9;font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}` +
    `@media (prefers-color-scheme: dark){body{background:#0b0b0b}}main{max-width:1040px;margin:0 auto;padding:48px 24px 80px}${REPORT_CSS}</style></head>` +
    `<body><main class="report">${bodyHtml}</main><div id="tip"></div><script>${TOOLTIP_JS}</script></body></html>`;
}
