"""Command line: `wca wrapped chat.zip` or `wca profile chat.zip --person Alice`."""
from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.prompt import Prompt

from . import __version__, ai, report, stats, terminal
from .parser import load

for _stream in (sys.stdout, sys.stderr):  # emojis and arrows must survive old Windows code pages and pipes
    if hasattr(_stream, "reconfigure") and (_stream.encoding or "").lower() not in ("utf-8", "utf8"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

console = Console()
err = Console(stderr=True)


def _date(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{value}' is not a date like 2024-03-31")


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("chat", help="WhatsApp export: the .txt file or the .zip WhatsApp creates")
    g = common.add_argument_group("time window")
    g.add_argument("--last", metavar="PERIOD", help="only the last part of the chat, e.g. 30d, 8w, 6m, 1y "
                   "(counted back from the last message)")
    g.add_argument("--since", type=_date, metavar="YYYY-MM-DD")
    g.add_argument("--until", type=_date, metavar="YYYY-MM-DD")
    g.add_argument("--date-order", choices=["dmy", "mdy", "ymd"],
                   help="date order in the export (detected automatically)")
    o = common.add_argument_group("output")
    o.add_argument("--html", metavar="FILE", help="save an HTML report (default: <chat>_wrapped.html)")
    o.add_argument("--no-html", action="store_true", help="don't write the HTML report")
    o.add_argument("--open", action="store_true", help="open the HTML report in the browser")
    o.add_argument("--json", metavar="FILE", help="save all numbers (and the AI text) as JSON")
    a = common.add_argument_group("AI (optional - without --ai nothing leaves your computer)")
    a.add_argument("--ai", choices=["claude", "openai"], help="add an AI-written analysis")
    a.add_argument("--model", help=f"model to use (defaults: {', '.join(f'{k}={v}' for k, v in ai.DEFAULT_MODELS.items())})")
    a.add_argument("--anonymize", action="store_true",
                   help="replace names with Person A/B... and mask phones, emails and links before sending")
    a.add_argument("--budget", type=int, default=150_000, metavar="CHARS",
                   help="max characters of chat sent to the AI, most recent first (default 150000)")
    a.add_argument("--lang", metavar="LANGUAGE", help="language of the AI text (default: the chat's language)")
    a.add_argument("--effort", choices=["low", "medium", "high"], default="medium",
                   help="Claude only: how hard the model thinks (default medium)")
    a.add_argument("-y", "--yes", action="store_true", help="don't ask before sending the chat to the AI")

    p = argparse.ArgumentParser(prog="wca", description="WhatsApp Chat Analyzer: your chat, wrapped.")
    p.add_argument("--version", action="version", version=f"wca {__version__}")
    sub = p.add_subparsers(dest="mode", required=True)
    sub.add_parser("wrapped", parents=[common], help="stats, awards and charts for the whole chat")
    pr = sub.add_parser("profile", parents=[common], help="one person's numbers and communication style")
    pr.add_argument("--person", help="exact name as it appears in the chat (asked if missing)")
    return p


def _pick_person(s: stats.ChatStats, wanted: str | None) -> stats.PersonStats:
    if wanted:
        found = s.person(wanted) or next((p for p in s.people if p.name.lower() == wanted.lower()), None)
        if not found:
            raise SystemExit(f"'{wanted}' is not in this chat. People: {', '.join(p.name for p in s.people)}")
        return found
    if not sys.stdin.isatty():
        raise SystemExit("Use --person to choose who to profile")
    for i, p in enumerate(s.people, 1):
        console.print(f"  [bold]{i}[/]. {p.name} [dim]({p.messages:,} messages)[/]")
    choice = Prompt.ask("Who?", choices=[str(i) for i in range(1, len(s.people) + 1)], default="1")
    return s.people[int(choice) - 1]


def _confirm_ai(args, n_people: int) -> None:
    if args.yes or not sys.stdin.isatty():
        return
    names = "names replaced by Person A, B..." if args.anonymize else "real names included (use --anonymize to hide them)"
    console.print(f"[yellow]The chat text (up to {args.budget:,} characters) will be sent to "
                  f"{'Anthropic' if args.ai == 'claude' else 'OpenAI'}; {names}.[/]")
    if n_people > 1:
        console.print("[dim]Make sure the people in this chat would be OK with that.[/]")
    if Prompt.ask("Continue?", choices=["y", "n"], default="y") != "y":
        raise SystemExit("Cancelled: no data was sent.")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    path = Path(args.chat)
    if not path.exists():
        err.print(f"[red]File not found:[/] {path}")
        return 1
    try:
        messages = load(path, args.date_order)
    except (ValueError, OSError) as e:
        err.print(f"[red]Can't read the chat:[/] {e}")
        return 1
    if not messages:
        err.print("[red]No messages found.[/] Is this a WhatsApp export (Chat → Export chat)?")
        return 1
    try:
        messages = stats.filter_messages(messages, args.since, args.until, args.last)
    except ValueError as e:
        err.print(f"[red]{e}[/]")
        return 1
    if not messages:
        err.print("[yellow]No messages in that time window.[/]")
        return 1

    s = stats.compute(messages)
    title = path.stem.replace("WhatsApp Chat with ", "").replace("WhatsApp Chat - ", "").replace("_", " ").strip()
    person = ai_wrapped = ai_profile = None

    if args.mode == "wrapped":
        terminal.show_wrapped(console, s, f"{title} · Wrapped")
    else:
        person = _pick_person(s, args.person)
        terminal.show_person(console, s, person)

    if args.ai:
        _confirm_ai(args, len(s.people))
        try:
            with console.status(f"Asking {args.ai}…"):
                kwargs = dict(provider=args.ai, model=args.model, budget=args.budget,
                              anonymize=args.anonymize, language=args.lang, effort=args.effort)
                if args.mode == "wrapped":
                    ai_wrapped = ai.wrapped(s, messages, **kwargs)
                else:
                    ai_profile = ai.profile(person.name, s, messages, **kwargs)
        except ai.AIError as e:
            err.print(f"[red]AI step failed:[/] {e}  [dim](the stats above are still valid)[/]")
        else:
            if ai_wrapped:
                terminal.show_ai_wrapped(console, ai_wrapped)
            if ai_profile:
                terminal.show_ai_profile(console, person.name, ai_profile)

    if not args.no_html:
        suffix = "wrapped" if args.mode == "wrapped" else f"profile_{person.name}"
        out = Path(args.html or path.with_name(f"{path.stem}_{suffix}.html"))
        page_title = f"{title} · Wrapped" if args.mode == "wrapped" else f"{person.name} · {title}"
        out.write_text(report.render(s, page_title, ai_wrapped, person, ai_profile), encoding="utf-8")
        console.print(f"\n[bold]Report:[/] {out.resolve()}")
        if args.open:
            webbrowser.open(out.resolve().as_uri())
    if args.json:
        data = {"stats": s.to_dict(), "person": person.name if person else None,
                "ai_wrapped": ai_wrapped, "ai_profile": ai_profile}
        Path(args.json).write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        console.print(f"[bold]JSON:[/] {Path(args.json).resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
