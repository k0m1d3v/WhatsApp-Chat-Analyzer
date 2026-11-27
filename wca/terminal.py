"""Rich terminal output."""
from __future__ import annotations

from rich import box
from rich.columns import Columns
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .stats import ChatStats, PersonStats, fmt_minutes

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
SHADES = " ░▒▓█"
ACCENT = "green3"


def _tile(value: str, label: str) -> Panel:
    return Panel(Text.assemble((value, f"bold {ACCENT}"), "\n", (label, "dim")), box=box.ROUNDED, padding=(0, 2))


def _overview(s: ChatStats) -> Columns:
    gap = s.longest_silence[0]
    return Columns([
        _tile(f"{s.total_messages:,}", "messages"),
        _tile(f"{s.total_words:,}", "words"),
        _tile(f"{s.active_days}/{s.span_days}", "days active"),
        _tile(f"{s.conversations:,}", "conversations"),
        _tile(f"{s.longest_streak[0]} days", "longest streak"),
        _tile(f"{gap.days} days" if gap.days else f"{gap.seconds // 3600} h", "longest silence"),
    ])


def _people_table(s: ChatStats, limit: int = 15) -> Table:
    t = Table(box=box.SIMPLE_HEAD, header_style="bold", title="People", title_justify="left")
    for col, just in [("Name", "left"), ("Messages", "right"), ("Share", "left"), ("Words/msg", "right"),
                      ("Reply time", "right"), ("Starts", "right"), ("Media", "right"), ("Top emoji", "center")]:
        t.add_column(col, justify=just)
    top = s.people[0].messages
    for p in s.people[:limit]:
        bar = "█" * max(1, round(16 * p.messages / top))
        t.add_row(p.name, f"{p.messages:,}", Text(f"{bar} {100 * p.messages / s.total_messages:.0f}%", ACCENT),
                  f"{p.avg_words:.1f}", fmt_minutes(p.median_reply_minutes), str(p.conversation_starts),
                  str(p.media), " ".join(e for e, _ in p.top_emojis[:3]) or "-")
    if len(s.people) > limit:
        t.caption = f"+ {len(s.people) - limit} more"
    return t


def _heatmap(s: ChatStats) -> Panel:
    peak = max(max(row) for row in s.heatmap) or 1
    lines = [Text("     " + "".join(f"{h:<3}" if h % 3 == 0 else "   " for h in range(24)), "dim")]
    for d, row in enumerate(s.heatmap):
        line = Text(f"{DAYS[d]}  ", "dim")
        for v in row:
            level = 0 if not v else 1 + round(3 * v / peak)
            line.append(SHADES[min(level, 4)] * 3, ACCENT)
        lines.append(line)
    return Panel(Group(*lines), title="When you chat (weekday x hour)", title_align="left", box=box.ROUNDED)


def _awards(s: ChatStats) -> Panel | None:
    if not s.awards:
        return None
    t = Table.grid(padding=(0, 2))
    for a in s.awards:
        t.add_row(a.emoji, Text(a.title, "bold"), a.winner, Text(a.detail, "dim"))
    return Panel(t, title="Awards", title_align="left", box=box.ROUNDED)


def _tops(emojis, words) -> Columns:
    e = Table(box=None, title="Top emojis", title_justify="left", show_header=False)
    e.add_column("")
    e.add_column("", justify="right")
    for em, n in emojis:
        e.add_row(em, f"{n:,}")
    w = Table(box=None, title="Top words", title_justify="left", show_header=False)
    w.add_column("")
    w.add_column("", justify="right")
    for word, n in words:
        w.add_row(word, f"{n:,}")
    return Columns([e, w], padding=(0, 6))


def show_wrapped(console: Console, s: ChatStats, title: str) -> None:
    console.print()
    console.rule(Text(f" {title} ", f"bold {ACCENT}"))
    console.print(Text(f"{s.first:%d %b %Y} → {s.last:%d %b %Y}  ·  {len(s.people)} people", "dim"),
                  justify="center")
    console.print()
    console.print(_overview(s))
    console.print(_people_table(s))
    if (aw := _awards(s)):
        console.print(aw)
    console.print(_heatmap(s))
    day, n = s.busiest_day
    console.print(Text.assemble("Busiest day: ", (f"{day:%A %d %B %Y}", "bold"), f" with {n:,} messages"))
    console.print()
    console.print(_tops(s.top_emojis, s.top_words))


def show_person(console: Console, s: ChatStats, p: PersonStats) -> None:
    console.print()
    console.rule(Text(f" {p.name} ", f"bold {ACCENT}"))
    console.print(Columns([
        _tile(f"{p.messages:,}", f"messages ({100 * p.messages / s.total_messages:.0f}%)"),
        _tile(f"{p.avg_words:.1f}", "words per message"),
        _tile(fmt_minutes(p.median_reply_minutes), "typical reply time"),
        _tile(str(p.conversation_starts), "conversations started"),
        _tile(f"{p.night_pct:.0f}%", "messages after midnight"),
        _tile(f"{p.emojis_per_message:.2f}", "emojis per message"),
    ]))
    console.print(_tops(p.top_emojis, p.top_words))


def show_ai_wrapped(console: Console, r: dict) -> None:
    body = [Text(r["vibe"], "bold italic"), Text()]
    body.append(Text("Topics & running jokes", f"bold {ACCENT}"))
    body += [Text.assemble("• ", (t["title"], "bold"), f" — {t['description']}") for t in r["topics"]]
    body += [Text(), Text("Memorable moments", f"bold {ACCENT}")]
    body += [Text.assemble("• ", (m["date"], "bold"), f" — {m['description']}") for m in r["moments"]]
    body += [Text(), Text("Who's who", f"bold {ACCENT}")]
    body += [Text.assemble("• ", (p["name"], "bold"), f" — {p['description']}") for p in r["people"]]
    body += [Text(), Text(r["closing"], "italic")]
    console.print(Panel(Group(*body), title="✨ AI recap", title_align="left", box=box.ROUNDED, padding=(1, 2)))


def show_ai_profile(console: Console, name: str, r: dict) -> None:
    body = [Text(r["summary"], "bold"), Text()]
    for sec in r["sections"]:
        body.append(Text(sec["title"], f"bold {ACCENT}"))
        body += [Text(f"• {pt}") for pt in sec["points"]]
        body.append(Text())
    body.append(Text("Tips", f"bold {ACCENT}"))
    body += [Text(f"• {tip}") for tip in r["tips"]]
    body += [Text(), Text(r["confidence"], "dim italic")]
    console.print(Panel(Group(*body), title=f"✨ How {name} communicates", title_align="left",
                        box=box.ROUNDED, padding=(1, 2)))
