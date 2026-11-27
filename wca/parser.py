"""Parse WhatsApp chat exports (iOS and Android, any date order, .txt or .zip)."""
from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Invisible marks WhatsApp sprinkles into exports (LRM, RLM, narrow/no-break spaces, BOM).
_INVISIBLE = dict.fromkeys(map(ord, "‎‏﻿"), None)
_SPACES = {ord(" "): " ", ord(" "): " "}

_DATE = r"(\d{1,4})[/.\-](\d{1,2})[/.\-](\d{1,4})"
_TIME = r"(\d{1,2})[:.](\d{2})(?:[:.](\d{2}))?\s*([AaPp]\.?\s?[Mm]\.?)?"

# iOS:     [25/12/23, 21:04:11] Alice: text
IOS = re.compile(rf"^\[{_DATE},?\s+{_TIME}\]\s+(.*)$")
# Android: 25/12/23, 21:04 - Alice: text
ANDROID = re.compile(rf"^{_DATE},?\s+{_TIME}\s+[-–]\s+(.*)$")

MEDIA_MARKERS = (
    "<media omitted>", "<media omessi>", "<media omesso>", "<multimedia omitido>",
    "image omitted", "video omitted", "audio omitted", "sticker omitted", "gif omitted",
    "document omitted", "contact card omitted",
    "immagine omessa", "video omesso", "audio omesso", "sticker omesso", "gif omessa",
    "documento omesso", "scheda contatto omessa",
    "<attached:", "<allegato:",
)
DELETED_MARKERS = (
    "this message was deleted", "you deleted this message",
    "questo messaggio è stato eliminato", "hai eliminato questo messaggio",
)
EDITED_MARKERS = ("<this message was edited>", "<questo messaggio è stato modificato>")
SYSTEM_MARKERS = (
    "end-to-end encrypted", "crittografati end-to-end", "crittografia end-to-end",
    "created group", "ha creato il gruppo", "added you", "ti ha aggiunto",
    "changed the subject", "ha cambiato l'oggetto", "changed this group's icon",
    "ha cambiato l'immagine di questo gruppo", "changed the group description",
    "joined using this group's invite link", "si è unito tramite il link",
    "security code changed", "codice di sicurezza", "is a contact", "è un contatto",
    "disappearing messages", "messaggi effimeri", "you're now an admin", "ora sei un amministratore",
)


@dataclass
class Message:
    ts: datetime
    sender: str
    text: str
    kind: str = "text"  # "text" | "media" | "deleted"


@dataclass
class _Raw:
    d: tuple[int, int, int]
    t: tuple[int, int, int, str | None]
    body: str
    android: bool


def read_export(path: str | Path) -> str:
    """Return the chat text from a .txt export or a .zip export (picks the chat .txt inside)."""
    path = Path(path)
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            txts = [n for n in z.namelist() if n.lower().endswith(".txt")]
            if not txts:
                raise ValueError(f"No .txt chat file inside {path.name}")
            name = next((n for n in txts if "chat" in n.lower()), txts[0])
            data = z.read(name)
    else:
        data = path.read_bytes()
    return io.TextIOWrapper(io.BytesIO(data), encoding="utf-8-sig", errors="replace").read()


def _match(line: str) -> _Raw | None:
    for pattern, android in ((IOS, False), (ANDROID, True)):
        m = pattern.match(line)
        if m:
            a, b, c, hh, mm, ss, ampm, body = m.groups()
            return _Raw((int(a), int(b), int(c)), (int(hh), int(mm), int(ss or 0), ampm), body, android)
    return None


def detect_date_order(raws: list[_Raw]) -> str:
    """'ymd', 'dmy' or 'mdy', from the values that appear in the file."""
    if any(r.d[0] > 31 for r in raws):
        return "ymd"
    if any(r.d[0] > 12 for r in raws):
        return "dmy"
    if any(r.d[1] > 12 for r in raws):
        return "mdy"
    return "dmy"  # ambiguous everywhere: day-first is the most common worldwide


def _to_datetime(r: _Raw, order: str) -> datetime | None:
    a, b, c = r.d
    year, month, day = {"ymd": (a, b, c), "dmy": (c, b, a), "mdy": (c, a, b)}[order]
    if year < 100:
        year += 2000
    hh, mm, ss, ampm = r.t
    if ampm:
        pm = ampm.lower().startswith("p")
        hh = hh % 12 + (12 if pm else 0)
    try:
        return datetime(year, month, day, hh, mm, ss)
    except ValueError:
        return None


def _classify(text: str) -> tuple[str, str]:
    low = text.lower().strip()
    for marker in EDITED_MARKERS:
        if low.endswith(marker):
            text = text[: len(text) - len(marker)].rstrip()
            low = text.lower().strip()
    if any(low.startswith(m) or low == m for m in MEDIA_MARKERS) or low.endswith(" omitted") or low.endswith(" omessa") or low.endswith(" omesso"):
        return "media", ""
    if any(m in low for m in DELETED_MARKERS) and len(low) < 60:
        return "deleted", ""
    return "text", text


def parse(text: str, date_order: str | None = None) -> list[Message]:
    """Parse the full text of an export into messages. Multi-line messages are kept whole."""
    entries: list[list] = []  # [_Raw, [lines]]
    for line in text.translate(_INVISIBLE).translate(_SPACES).splitlines():
        raw = _match(line)
        if raw:
            entries.append([raw, [raw.body]])
        elif entries:
            entries[-1][1].append(line)  # continuation of a multi-line message

    raws = [e[0] for e in entries]
    order = date_order or detect_date_order(raws)
    messages: list[Message] = []
    for raw, lines in entries:
        body = "\n".join(lines)
        sender, sep, content = body.partition(": ")
        if not sep or len(sender) > 60:
            continue  # system line with no sender (Android)
        if any(m in content.lower() for m in SYSTEM_MARKERS) and len(content) < 200:
            continue
        ts = _to_datetime(raw, order)
        if ts is None:
            continue
        kind, clean = _classify(content)
        messages.append(Message(ts, sender.strip(), clean.strip(), kind))
    messages.sort(key=lambda m: m.ts)
    return messages


def load(path: str | Path, date_order: str | None = None) -> list[Message]:
    return parse(read_export(path), date_order)
