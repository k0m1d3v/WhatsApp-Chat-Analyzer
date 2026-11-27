"""Everything we can say about a chat without any AI: counts, rhythms, habits, records."""
from __future__ import annotations

import re
import statistics
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta

import emoji

from .parser import Message

# A silence longer than this starts a new conversation (and is not a "reply").
CONVERSATION_GAP = timedelta(hours=4)
NIGHT_HOURS = range(0, 5)

URL = re.compile(r"https?://\S+|www\.\S+", re.I)
WORD = re.compile(r"[^\W\d_]{3,}", re.UNICODE)
LAUGH = re.compile(r"\b(?:a?h[ae]h[ae]\w*|(?:ha){2,}\w*|(?:ah){2,}\w*|lol+|lmao+|xd+)\b", re.I)

STOPWORDS = set("""
the and for are but not you all any can had her was one our out has him his how its may new now old see two way who
did get got let say she too use that with have this will your from they know want been good much some time very when
come here just like long make many more only over such take than them well were what where which while would there
their then these those about after again also because before being could doing does dont down each even every into
just more most other should since still thing think through under until yeah yes okay really going gonna im its
che non per una del della delle dei degli con come anche sono sei ma più piu cosa questo questa quello quella ho hai
ha abbiamo avete hanno era ero eri sta sto stai fare fatto fai faccio ci si se mi ti lo la le li gli un uno nel nella
nei negli dal dalla alla allo alle agli sul sulla poi già gia ancora quando dove perché perche perchè quindi però pero
tutto tutti tutta tutte molto poco bene male oggi domani ieri adesso ora qui qua lì là così cosi solo sempre mai niente
nulla qualcosa tipo boh comunque magari anzi infatti oppure mentre dopo prima allora essere avere sia siamo siete sui
""".split())


@dataclass
class PersonStats:
    name: str
    messages: int = 0
    words: int = 0
    media: int = 0
    links: int = 0
    deleted: int = 0
    emojis: int = 0
    laughs: int = 0
    questions: int = 0
    conversation_starts: int = 0
    night_messages: int = 0
    longest_message_words: int = 0
    reply_seconds: list[float] = field(default_factory=list, repr=False)
    top_emojis: list[tuple[str, int]] = field(default_factory=list)
    top_words: list[tuple[str, int]] = field(default_factory=list)

    @property
    def avg_words(self) -> float:
        texts = self.messages - self.media - self.deleted
        return self.words / texts if texts else 0.0

    @property
    def median_reply_minutes(self) -> float | None:
        return statistics.median(self.reply_seconds) / 60 if self.reply_seconds else None

    @property
    def night_pct(self) -> float:
        return 100 * self.night_messages / self.messages if self.messages else 0.0

    @property
    def emojis_per_message(self) -> float:
        return self.emojis / self.messages if self.messages else 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("reply_seconds")
        d.update(avg_words=round(self.avg_words, 2), median_reply_minutes=self.median_reply_minutes,
                 night_pct=round(self.night_pct, 2), emojis_per_message=round(self.emojis_per_message, 3))
        return d


@dataclass
class Award:
    title: str
    emoji: str
    winner: str
    detail: str


@dataclass
class ChatStats:
    people: list[PersonStats]
    total_messages: int
    total_words: int
    first: datetime
    last: datetime
    active_days: int
    conversations: int
    busiest_day: tuple[date, int]
    longest_streak: tuple[int, date, date]
    longest_silence: tuple[timedelta, datetime, datetime]
    heatmap: list[list[int]]                  # [weekday 0=Mon][hour]
    monthly: dict[str, dict[str, int]]        # "YYYY-MM" -> {person: count}
    top_emojis: list[tuple[str, int]]
    top_words: list[tuple[str, int]]
    awards: list[Award]

    @property
    def span_days(self) -> int:
        return (self.last.date() - self.first.date()).days + 1

    @property
    def is_group(self) -> bool:
        return len(self.people) > 2

    def person(self, name: str) -> PersonStats | None:
        return next((p for p in self.people if p.name == name), None)

    def to_dict(self) -> dict:
        streak, s_from, s_to = self.longest_streak
        gap, g_from, g_to = self.longest_silence
        return {
            "people": [p.to_dict() for p in self.people],
            "total_messages": self.total_messages,
            "total_words": self.total_words,
            "first": self.first.isoformat(),
            "last": self.last.isoformat(),
            "span_days": self.span_days,
            "active_days": self.active_days,
            "conversations": self.conversations,
            "busiest_day": {"date": self.busiest_day[0].isoformat(), "messages": self.busiest_day[1]},
            "longest_streak": {"days": streak, "from": s_from.isoformat(), "to": s_to.isoformat()},
            "longest_silence": {"days": round(gap.total_seconds() / 86400, 1),
                                "from": g_from.isoformat(), "to": g_to.isoformat()},
            "heatmap_weekday_hour": self.heatmap,
            "monthly": self.monthly,
            "top_emojis": self.top_emojis,
            "top_words": self.top_words,
            "awards": [asdict(a) for a in self.awards],
        }


def _words(text: str) -> list[str]:
    return [w for w in WORD.findall(URL.sub(" ", text).lower()) if w not in STOPWORDS]


def _streak(days: list[date]) -> tuple[int, date, date]:
    best = (1, days[0], days[0])
    start = prev = days[0]
    for d in days[1:]:
        if d - prev != timedelta(days=1):
            start = d
        if (d - start).days + 1 > best[0]:
            best = ((d - start).days + 1, start, d)
        prev = d
    return best


def _awards(people: list[PersonStats]) -> list[Award]:
    if len(people) < 2:
        return []
    awards = []

    def give(title, icon, key, fmt, eligible=lambda p: True, reverse=True):
        pool = [p for p in people if eligible(p) and key(p) is not None]
        if pool:
            w = sorted(pool, key=key, reverse=reverse)[0]
            if reverse and not key(w):
                return  # nobody earned it (e.g. zero laughs)
            awards.append(Award(title, icon, w.name, fmt(w)))

    active = lambda p: p.messages >= 20  # noqa: E731 - avoid crowning someone with 3 messages
    give("Chatterbox", "💬", lambda p: p.messages, lambda p: f"{p.messages:,} messages")
    give("Novelist", "📜", lambda p: p.avg_words, lambda p: f"{p.avg_words:.1f} words per message", active)
    give("Speed Demon", "⚡", lambda p: p.median_reply_minutes, lambda p: f"replies in ~{_fmt_minutes(p.median_reply_minutes)}",
         lambda p: len(p.reply_seconds) >= 10, reverse=False)
    give("Ice Breaker", "🧊", lambda p: p.conversation_starts, lambda p: f"started {p.conversation_starts} conversations")
    give("Night Owl", "🦉", lambda p: p.night_pct, lambda p: f"{p.night_pct:.0f}% of messages between 0:00 and 5:00", active)
    give("Emoji Royalty", "👑", lambda p: p.emojis_per_message, lambda p: f"{p.emojis_per_message:.2f} emojis per message", active)
    give("Comedian", "😂", lambda p: p.laughs, lambda p: f"{p.laughs} laughs (haha, lol, 😂...)")
    give("Curious Mind", "❓", lambda p: p.questions, lambda p: f"asked {p.questions} questions")
    give("Photographer", "📸", lambda p: p.media, lambda p: f"{p.media} photos, videos and stickers")
    return awards


def _fmt_minutes(m: float | None) -> str:
    if m is None:
        return "-"
    if m < 1:
        return f"{m * 60:.0f}s"
    if m < 90:
        return f"{m:.0f} min"
    return f"{m / 60:.1f} h"


fmt_minutes = _fmt_minutes


def compute(messages: list[Message], top_n: int = 10) -> ChatStats:
    if not messages:
        raise ValueError("No messages to analyze")
    people: dict[str, PersonStats] = {}
    emoji_by: dict[str, Counter] = defaultdict(Counter)
    words_by: dict[str, Counter] = defaultdict(Counter)
    heatmap = [[0] * 24 for _ in range(7)]
    monthly: dict[str, Counter] = defaultdict(Counter)
    per_day: Counter = Counter()
    all_emojis: Counter = Counter()  # filled in message order, so ties rank the same as in the web version
    all_words: Counter = Counter()
    conversations = 0
    silence = (timedelta(0), messages[0].ts, messages[0].ts)

    prev: Message | None = None
    for m in messages:
        p = people.setdefault(m.sender, PersonStats(m.sender))
        p.messages += 1
        heatmap[m.ts.weekday()][m.ts.hour] += 1
        monthly[m.ts.strftime("%Y-%m")][m.sender] += 1
        per_day[m.ts.date()] += 1
        if m.ts.hour in NIGHT_HOURS:
            p.night_messages += 1

        gap = m.ts - prev.ts if prev else None
        if prev is None or gap > CONVERSATION_GAP:
            conversations += 1
            p.conversation_starts += 1
        elif m.sender != prev.sender:
            p.reply_seconds.append(gap.total_seconds())
        if gap and gap > silence[0]:
            silence = (gap, prev.ts, m.ts)
        prev = m

        if m.kind == "media":
            p.media += 1
            continue
        if m.kind == "deleted":
            p.deleted += 1
            continue
        n_words = len(m.text.split())
        p.words += n_words
        p.longest_message_words = max(p.longest_message_words, n_words)
        p.links += len(URL.findall(m.text))
        found = [e["emoji"] for e in emoji.emoji_list(m.text)]
        p.emojis += len(found)
        emoji_by[m.sender].update(found)
        all_emojis.update(found)
        p.laughs += len(LAUGH.findall(m.text)) + sum(found.count(e) for e in ("😂", "🤣", "😆"))
        p.questions += m.text.count("?") > 0
        words = _words(m.text)
        words_by[m.sender].update(words)
        all_words.update(words)

    for name, p in people.items():
        p.top_emojis = emoji_by[name].most_common(top_n)
        p.top_words = words_by[name].most_common(top_n)

    ranked = sorted(people.values(), key=lambda p: p.messages, reverse=True)
    days = sorted(per_day)
    busiest = max(per_day.items(), key=lambda kv: kv[1])
    return ChatStats(
        people=ranked,
        total_messages=len(messages),
        total_words=sum(p.words for p in ranked),
        first=messages[0].ts,
        last=messages[-1].ts,
        active_days=len(days),
        conversations=conversations,
        busiest_day=busiest,
        longest_streak=_streak(days),
        longest_silence=silence,
        heatmap=heatmap,
        monthly={k: dict(v) for k, v in sorted(monthly.items())},
        top_emojis=all_emojis.most_common(top_n),
        top_words=all_words.most_common(top_n),
        awards=_awards(ranked),
    )


def parse_period(spec: str) -> timedelta:
    """'3w', '10d', '6m', '1y' -> timedelta."""
    m = re.fullmatch(r"\s*(\d+)\s*([dwmy])\s*", spec.lower())
    if not m:
        raise ValueError(f"Invalid period '{spec}': use e.g. 10d, 3w, 6m, 1y")
    n, unit = int(m.group(1)), m.group(2)
    return timedelta(days=n * {"d": 1, "w": 7, "m": 30, "y": 365}[unit])


def filter_messages(messages: list[Message], since: datetime | None = None, until: datetime | None = None,
                    last: str | None = None) -> list[Message]:
    """Keep a time window. --last counts back from the chat's last message, not from today."""
    if last and messages:
        since = max(since or datetime.min, messages[-1].ts - parse_period(last))
    return [m for m in messages if (since is None or m.ts >= since) and (until is None or m.ts <= until)]
