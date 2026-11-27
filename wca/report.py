"""Self-contained HTML report: inline SVG charts, light and dark mode, no external files."""
from __future__ import annotations

import math
from datetime import datetime
from html import escape

from .stats import ChatStats, PersonStats, fmt_minutes

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
N_SERIES = 7  # people beyond this fold into "Others"
HEAT_STEPS = 7  # sequential blue ramp, light->dark on light, dark->light on dark

CSS = """
:root { color-scheme: light;
  --page:#f9f9f9; --surface:#ffffff; --ink:#191919; --ink-2:#666666; --grid:#e7e7e7; --axis:#c2c2c2;
  --ring:rgba(11,11,11,.10); --empty:#f1f1f1; --accent:#257de0;
  --s1:#257de0; --s2:#f47230; --s3:#00b894; --s4:#f2a600; --s5:#ee7fac; --s6:#008a17; --s7:#6a4ce2; --s8:#9c9c9c;
  --h0:#cce3fd; --h1:#9dc8f7; --h2:#6aabf1; --h3:#338ced; --h4:#2370cd; --h5:#1757ac; --h6:#0e3d7e; }
@media (prefers-color-scheme: dark) { :root { color-scheme: dark;
  --page:#0b0b0b; --surface:#191919; --ink:#efefef; --ink-2:#9c9c9c; --grid:#303030; --axis:#474747;
  --ring:rgba(255,255,255,.10); --empty:#222222; --accent:#338ced;
  --s1:#338ced; --s2:#e76624; --s3:#00a888; --s4:#d28e05; --s5:#e24d8b; --s6:#0aac23; --s7:#9887ef; --s8:#5e5e5e;
  --h0:#0e3d7e; --h1:#1757ac; --h2:#2370cd; --h3:#338ced; --h4:#6aabf1; --h5:#9dc8f7; --h6:#cce3fd; } }
* { box-sizing: border-box; }
body { margin:0; background:var(--page); color:var(--ink); font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif; }
main { max-width: 1040px; margin: 0 auto; padding: 48px 24px 80px; }
header h1 { font-size: 40px; line-height:1.1; margin: 0 0 6px; letter-spacing:-.02em; }
header p { color: var(--ink-2); margin: 0; }
section { background: var(--surface); border-radius: 16px; box-shadow: 0 0 0 1px var(--ring); padding: 24px; margin-top: 20px; }
h2 { font-size: 18px; margin: 0 0 4px; }
.sub { color: var(--ink-2); margin: 0 0 16px; font-size: 14px; }
.tiles { display:grid; grid-template-columns: repeat(auto-fill, minmax(150px,1fr)); gap: 12px; margin-top: 28px; }
.tile { background: var(--surface); border-radius: 14px; box-shadow: 0 0 0 1px var(--ring); padding: 16px 18px; }
.tile b { display:block; font-size: 28px; line-height:1.15; }
.tile span { color: var(--ink-2); font-size: 13px; }
.grid2 { display:grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.grid2 > section { margin-top: 0; }
@media (max-width: 760px) { .grid2 { grid-template-columns: 1fr; } }
.awards { display:grid; grid-template-columns: repeat(auto-fill, minmax(220px,1fr)); gap: 12px; }
.award { border-radius: 12px; box-shadow: 0 0 0 1px var(--ring); padding: 14px 16px; }
.award .e { font-size: 26px; } .award b { display:block; } .award span { color: var(--ink-2); font-size: 13px; }
table { border-collapse: collapse; width: 100%; font-variant-numeric: tabular-nums; }
th, td { text-align: right; padding: 7px 10px; border-bottom: 1px solid var(--grid); white-space: nowrap; }
th:first-child, td:first-child { text-align: left; } th { color: var(--ink-2); font-weight: 500; font-size: 13px; }
.swatch { display:inline-block; width:10px; height:10px; border-radius:3px; margin-right:8px; vertical-align: baseline; }
.legend { display:flex; flex-wrap:wrap; gap: 4px 16px; color: var(--ink-2); font-size: 13px; margin-bottom: 8px; }
ol.rank { margin:0; padding:0; list-style:none; }
ol.rank li { display:flex; justify-content:space-between; padding: 6px 0; border-bottom: 1px solid var(--grid); }
ol.rank li span:last-child { color: var(--ink-2); font-variant-numeric: tabular-nums; }
.emoji li span:first-child { font-size: 20px; }
svg { display:block; width:100%; height:auto; overflow: visible; }
svg text { fill: var(--ink-2); font-size: 12px; font-family: inherit; }
svg .grid { stroke: var(--grid); stroke-width: 1; } svg .axis { stroke: var(--axis); stroke-width: 1; }
svg [data-tip]:hover { opacity: .8; }
.ai p { margin: 0 0 12px; } .ai h3 { font-size: 15px; margin: 18px 0 6px; }
.ai ul { margin: 0; padding-left: 20px; } .ai li { margin: 4px 0; }
.vibe { font-size: 20px; font-weight: 600; }
.note { color: var(--ink-2); font-size: 13px; }
#tip { position: fixed; pointer-events: none; background: var(--ink); color: var(--surface); padding: 6px 10px;
  border-radius: 8px; font-size: 13px; opacity: 0; transition: opacity .1s; white-space: pre; z-index: 9; }
footer { color: var(--ink-2); font-size: 13px; margin-top: 32px; text-align: center; }
"""

TOOLTIP_JS = """
const tip = document.getElementById('tip');
document.addEventListener('mousemove', e => {
  const t = e.target.closest('[data-tip]');
  if (!t) { tip.style.opacity = 0; return; }
  tip.textContent = t.dataset.tip; tip.style.opacity = 1;
  const x = Math.min(e.clientX + 14, innerWidth - tip.offsetWidth - 8);
  tip.style.left = x + 'px'; tip.style.top = (e.clientY + 14) + 'px';
});
addEventListener('scroll', () => { tip.style.opacity = 0; }, {passive: true});
"""


def _e(x) -> str:
    return escape(str(x), quote=True)


def _nice_ticks(peak: float, n: int = 4) -> list[float]:
    if peak <= 0:
        return [0, 1]
    raw = peak / n
    mag = 10 ** math.floor(math.log10(raw))
    step = next(s * mag for s in (1, 2, 2.5, 5, 10) if s * mag >= raw)
    return [i * step for i in range(int(math.ceil(peak / step)) + 1)]


def _fmt_tick(v: float) -> str:
    return f"{v / 1000:g}K" if v >= 10_000 else f"{v:,.0f}"


def _colors(people: list[PersonStats]) -> dict[str, str]:
    """Color follows the person (fixed slot by rank), never re-assigned by a chart."""
    return {p.name: f"var(--s{i + 1})" if i < N_SERIES else "var(--s8)" for i, p in enumerate(people)}


def _hbar(rows: list[tuple[str, float, str, str]], width=400, unit_fmt=lambda v: f"{v:,.0f}") -> str:
    """Horizontal bars: (label, value, color, tooltip). Label left, value at the bar tip."""
    label_w, row_h, bar_h, value_w = 110, 30, 18, 60
    plot_w = width - label_w - value_w
    peak = max((v for _, v, _, _ in rows), default=1) or 1
    h = row_h * len(rows)
    out = [f'<svg viewBox="0 0 {width} {h}" role="img">']
    for i, (label, v, color, tip) in enumerate(rows):
        y = i * row_h + (row_h - bar_h) / 2
        w = max(2.0, plot_w * v / peak)
        r = min(4, w / 2)
        x0 = label_w
        path = (f"M{x0},{y} H{x0 + w - r} Q{x0 + w},{y} {x0 + w},{y + r} V{y + bar_h - r} "
                f"Q{x0 + w},{y + bar_h} {x0 + w - r},{y + bar_h} H{x0} Z")
        short = label if len(label) <= 18 else label[:17] + "…"
        out.append(f'<text x="{label_w - 10}" y="{y + bar_h / 2 + 4}" text-anchor="end" style="fill:var(--ink)">{_e(short)}</text>')
        out.append(f'<path d="{path}" style="fill:{color}" data-tip="{_e(tip)}"/>')
        out.append(f'<text x="{x0 + w + 8}" y="{y + bar_h / 2 + 4}">{_e(unit_fmt(v))}</text>')
    out.append("</svg>")
    return "".join(out)


def _heatmap(s: ChatStats) -> str:
    cell, gap, left, top = 30, 2, 40, 22
    width, height = left + 24 * cell, top + 7 * cell
    peak = max(max(r) for r in s.heatmap) or 1
    out = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Messages by weekday and hour">']
    for hr in range(0, 24, 3):
        out.append(f'<text x="{left + hr * cell + cell / 2}" y="14" text-anchor="middle">{hr}:00</text>')
    for d, row in enumerate(s.heatmap):
        y = top + d * cell
        out.append(f'<text x="{left - 8}" y="{y + cell / 2 + 4}" text-anchor="end">{DAYS[d]}</text>')
        for hr, v in enumerate(row):
            if v:
                fill = f"var(--h{min(HEAT_STEPS - 1, int(HEAT_STEPS * v / (peak + 1)))})"
            else:
                fill = "var(--empty)"
            tip = f"{DAYS[d]} {hr:02d}:00–{hr:02d}:59\n{v:,} messages"
            out.append(f'<rect x="{left + hr * cell + gap / 2}" y="{y + gap / 2}" width="{cell - gap}" '
                       f'height="{cell - gap}" rx="4" style="fill:{fill}" data-tip="{_e(tip)}"/>')
    out.append("</svg>")
    return "".join(out)


def _timeline(s: ChatStats, colors: dict[str, str]) -> tuple[str, str]:
    """Messages per month. One line per person for small chats, one total line for groups."""
    months = list(s.monthly)
    if len(s.people) <= 4:
        series = [(p.name, [s.monthly[m].get(p.name, 0) for m in months], colors[p.name]) for p in s.people]
    else:
        series = [("All messages", [sum(s.monthly[m].values()) for m in months], "var(--s1)")]
    width, height, left, right, top, bottom = 900, 260, 48, 110, 12, 28
    pw, ph = width - left - right, height - top - bottom
    ticks = _nice_ticks(max(max(v) for _, v, _ in series))
    ymax = ticks[-1] or 1
    x = (lambda i: left + pw / 2) if len(months) == 1 else (lambda i: left + pw * i / (len(months) - 1))
    y = lambda v: top + ph - ph * v / ymax  # noqa: E731
    out = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Messages per month">']
    for t in ticks:
        out.append(f'<line class="{"axis" if t == 0 else "grid"}" x1="{left}" x2="{left + pw}" y1="{y(t)}" y2="{y(t)}"/>')
        out.append(f'<text x="{left - 8}" y="{y(t) + 4}" text-anchor="end">{_fmt_tick(t)}</text>')
    every = max(1, math.ceil(len(months) / 10))
    for i, m in enumerate(months):
        if i % every == 0:
            label = datetime.strptime(m, "%Y-%m").strftime("%b %y")
            out.append(f'<text x="{x(i)}" y="{height - 8}" text-anchor="middle">{label}</text>')
    ends = sorted(y(v[-1]) for _, v, _ in series)
    end_labels = all(b - a >= 16 for a, b in zip(ends, ends[1:]))  # colliding labels: the legend carries identity
    for name, values, color in series:
        pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(values))
        if len(series) == 1:
            area = f"{x(0):.1f},{y(0):.1f} {pts} {x(len(values) - 1):.1f},{y(0):.1f}"
            out.append(f'<polygon points="{area}" style="fill:{color};opacity:.1"/>')
        out.append(f'<polyline points="{pts}" fill="none" style="stroke:{color}" stroke-width="2" '
                   f'stroke-linejoin="round" stroke-linecap="round"/>')
        last = len(values) - 1
        out.append(f'<circle cx="{x(last)}" cy="{y(values[last])}" r="4" style="fill:{color};stroke:var(--surface)" stroke-width="2"/>')
        if end_labels:
            short = name if len(name) <= 14 else name[:13] + "…"
            out.append(f'<text x="{x(last) + 10}" y="{y(values[last]) + 4}" style="fill:var(--ink)">{_e(short)}</text>')
    # hover columns: one invisible target per month with every series' value
    col_w = pw / max(1, len(months) - 1) if len(months) > 1 else pw
    for i, m in enumerate(months):
        label = datetime.strptime(m, "%Y-%m").strftime("%B %Y")
        tip = label + "".join(f"\n{n}: {v[i]:,}" for n, v, _ in series)
        out.append(f'<rect x="{x(i) - col_w / 2}" y="{top}" width="{col_w}" height="{ph}" fill="transparent" data-tip="{_e(tip)}"/>')
    out.append("</svg>")
    legend = ""
    if len(series) > 1:
        legend = '<div class="legend">' + "".join(
            f'<span><i class="swatch" style="background:{c}"></i>{_e(n)}</span>' for n, _, c in series) + "</div>"
    return legend, "".join(out)


def _rank_list(items: list[tuple[str, int]], cls: str = "") -> str:
    if not items:
        return '<p class="note">Nothing here.</p>'
    return f'<ol class="rank {cls}">' + "".join(
        f"<li><span>{_e(k)}</span><span>{n:,}</span></li>" for k, n in items) + "</ol>"


def _people_table(s: ChatStats, colors: dict[str, str]) -> str:
    rows = "".join(
        f'<tr><td><i class="swatch" style="background:{colors[p.name]}"></i>{_e(p.name)}</td>'
        f"<td>{p.messages:,}</td><td>{100 * p.messages / s.total_messages:.0f}%</td><td>{p.avg_words:.1f}</td>"
        f"<td>{_e(fmt_minutes(p.median_reply_minutes))}</td><td>{p.conversation_starts:,}</td>"
        f"<td>{p.media:,}</td><td>{p.emojis:,}</td><td>{p.night_pct:.0f}%</td></tr>"
        for p in s.people)
    return ("<table><thead><tr><th>Name</th><th>Messages</th><th>Share</th><th>Words/msg</th><th>Reply time</th>"
            "<th>Starts</th><th>Media</th><th>Emojis</th><th>Night</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>")


def _ai_wrapped(r: dict) -> str:
    li = lambda items: "<ul>" + "".join(items) + "</ul>"  # noqa: E731
    return (f'<section class="ai"><h2>✨ AI recap</h2><p class="vibe">{_e(r["vibe"])}</p>'
            "<h3>Topics &amp; running jokes</h3>"
            + li(f"<li><b>{_e(t['title'])}</b> — {_e(t['description'])}</li>" for t in r["topics"])
            + "<h3>Memorable moments</h3>"
            + li(f"<li><b>{_e(m['date'])}</b> — {_e(m['description'])}</li>" for m in r["moments"])
            + "<h3>Who's who</h3>"
            + li(f"<li><b>{_e(p['name'])}</b> — {_e(p['description'])}</li>" for p in r["people"])
            + f'<p style="margin-top:16px"><i>{_e(r["closing"])}</i></p></section>')


def _ai_profile(name: str, r: dict) -> str:
    parts = [f'<section class="ai"><h2>✨ How {_e(name)} communicates</h2><p class="vibe">{_e(r["summary"])}</p>']
    for sec in r["sections"]:
        parts.append(f"<h3>{_e(sec['title'])}</h3><ul>" + "".join(f"<li>{_e(p)}</li>" for p in sec["points"]) + "</ul>")
    parts.append("<h3>Tips</h3><ul>" + "".join(f"<li>{_e(t)}</li>" for t in r["tips"]) + "</ul>")
    parts.append(f'<p class="note" style="margin-top:16px">{_e(r["confidence"])}</p></section>')
    return "".join(parts)


def _tiles(items: list[tuple[str, str]]) -> str:
    return '<div class="tiles">' + "".join(
        f'<div class="tile"><b>{_e(v)}</b><span>{_e(k)}</span></div>' for v, k in items) + "</div>"


def render(s: ChatStats, title: str, ai_wrapped: dict | None = None, person: PersonStats | None = None,
           ai_profile: dict | None = None) -> str:
    colors = _colors(s.people)
    streak, st_from, st_to = s.longest_streak
    gap, g_from, g_to = s.longest_silence
    shown = s.people[:N_SERIES]
    others = s.people[N_SERIES:]
    bar_rows = [(p.name, p.messages, colors[p.name], f"{p.name}\n{p.messages:,} messages") for p in shown]
    if others:
        n = sum(p.messages for p in others)
        bar_rows.append((f"Others ({len(others)})", n, "var(--s8)", f"{len(others)} more people\n{n:,} messages"))
    reply_rows = [(p.name, p.median_reply_minutes, colors[p.name],
                   f"{p.name}\ntypical reply: {fmt_minutes(p.median_reply_minutes)}\n({len(p.reply_seconds):,} replies)")
                  for p in sorted(shown, key=lambda p: p.median_reply_minutes or 1e9) if p.median_reply_minutes is not None]
    legend, timeline = _timeline(s, colors)
    day, day_n = s.busiest_day

    body = [f"<header><h1>{_e(title)}</h1><p>{s.first:%d %b %Y} → {s.last:%d %b %Y} · "
            f"{len(s.people)} people</p></header>"]
    body.append(_tiles([
        (f"{s.total_messages:,}", "messages"), (f"{s.total_words:,}", "words"),
        (f"{s.active_days}/{s.span_days}", "days with messages"), (f"{s.conversations:,}", "conversations"),
        (f"{streak} days", f"streak · {st_from:%d %b} → {st_to:%d %b %Y}"),
        (f"{gap.days} days" if gap.days else f"{gap.seconds // 3600} h", f"longest silence · from {g_from:%d %b %Y}"),
    ]))
    if person:
        body.append('<section><h2>' + _e(person.name) + '</h2><p class="sub">Their numbers in this chat</p>' + _tiles([
            (f"{person.messages:,}", f"messages · {100 * person.messages / s.total_messages:.0f}% of the chat"),
            (f"{person.avg_words:.1f}", "words per message"),
            (fmt_minutes(person.median_reply_minutes), "typical reply time"),
            (f"{person.conversation_starts:,}", "conversations started"),
            (f"{person.night_pct:.0f}%", "messages 0:00–5:00"),
            (f"{person.emojis_per_message:.2f}", "emojis per message"),
        ]) + '<div class="grid2" style="margin-top:20px"><div><h2>Their emojis</h2>'
            + _rank_list(person.top_emojis, "emoji") + "</div><div><h2>Their words</h2>"
            + _rank_list(person.top_words) + "</div></div></section>")
        if ai_profile:
            body.append(_ai_profile(person.name, ai_profile))
    if ai_wrapped:
        body.append(_ai_wrapped(ai_wrapped))
    if s.awards:
        body.append('<section><h2>Awards</h2><p class="sub">Who wins what</p><div class="awards">' + "".join(
            f'<div class="award"><div class="e">{_e(a.emoji)}</div><b>{_e(a.title)}</b>{_e(a.winner)}'
            f"<br><span>{_e(a.detail)}</span></div>" for a in s.awards) + "</div></section>")
    body.append('<div class="grid2" style="margin-top:20px">')
    body.append(f'<section><h2>Who talks the most</h2><p class="sub">Messages per person</p>{_hbar(bar_rows)}</section>')
    if reply_rows:
        body.append('<section><h2>Who replies fastest</h2><p class="sub">Typical (median) time to reply, '
                    f'within a conversation</p>{_hbar(reply_rows, unit_fmt=fmt_minutes)}</section>')
    body.append("</div>")
    body.append(f'<section><h2>When you chat</h2><p class="sub">Messages by weekday and hour · busiest day: '
                f'{day:%A %d %B %Y} ({day_n:,} messages)</p>{_heatmap(s)}</section>')
    body.append(f'<section><h2>Over time</h2><p class="sub">Messages per month</p>{legend}{timeline}</section>')
    body.append('<div class="grid2" style="margin-top:20px">'
                f'<section><h2>Top emojis</h2>{_rank_list(s.top_emojis, "emoji")}</section>'
                f'<section><h2>Top words</h2>{_rank_list(s.top_words)}</section></div>')
    body.append(f'<section><h2>Everyone</h2><p class="sub">The full numbers</p>{_people_table(s, colors)}</section>')
    body.append(f"<footer>Made with WhatsApp Chat Analyzer · {datetime.now():%d %b %Y}"
                + (" · AI text is generated and may be wrong" if ai_wrapped or ai_profile else "") + "</footer>")

    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            f"<title>{_e(title)}</title><style>{CSS}</style></head><body><main>"
            + "".join(body) + f'</main><div id="tip"></div><script>{TOOLTIP_JS}</script></body></html>')
