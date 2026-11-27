"""Optional AI layer: a 'Wrapped' recap of the chat, or one person's communication style.

Providers: Claude (Anthropic) or OpenAI. Nothing here runs unless --ai is given.
"""
from __future__ import annotations

import json
import re
import string
from dataclasses import dataclass

from .parser import Message
from .stats import ChatStats

DEFAULT_MODELS = {"claude": "claude-opus-5-5", "openai": "gpt-4.1-mini"}

PHONE = re.compile(r"(?<![\w-])\+?\d(?:[ \-]?\d){8,14}(?![\w-])")  # 9+ digits, so dates don't match
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
URL = re.compile(r"https?://\S+|www\.\S+", re.I)

GROUND_RULES = """\
Ground rules:
- Base every statement on the transcript or the stats. If something can't be inferred, say so.
- Describe how people communicate, not who they are: no diagnoses, no personality disorders, no mental-health,
  health, sexuality, religion or other sensitive speculation, no judgments of character.
- Be warm and playful, never mocking. Write as if every participant will read it.
- Quote sparingly (a few words at most) and never quote anything that looks private or sensitive.
"""

WRAPPED_SYSTEM = (
    "You write the 'Wrapped' recap of a WhatsApp chat: a fun, warm end-of-year style summary that the people "
    "in the chat will enjoy reading together.\n" + GROUND_RULES
)
PROFILE_SYSTEM = (
    "You describe one person's communication style in a WhatsApp chat, to help others understand how they "
    "communicate. It is not a psychological assessment.\n" + GROUND_RULES
)

WRAPPED_SCHEMA = {
    "type": "object",
    "properties": {
        "vibe": {"type": "string", "description": "One sentence capturing the vibe of this chat."},
        "topics": {"type": "array", "description": "3-6 recurring topics or running jokes.", "items": {
            "type": "object", "properties": {"title": {"type": "string"}, "description": {"type": "string"}},
            "required": ["title", "description"], "additionalProperties": False}},
        "moments": {"type": "array", "description": "3-5 memorable moments, with their date.", "items": {
            "type": "object", "properties": {"date": {"type": "string"}, "description": {"type": "string"}},
            "required": ["date", "description"], "additionalProperties": False}},
        "people": {"type": "array", "description": "How each participant shows up in the chat (max 8).", "items": {
            "type": "object", "properties": {"name": {"type": "string"}, "description": {"type": "string"}},
            "required": ["name", "description"], "additionalProperties": False}},
        "closing": {"type": "string", "description": "A short, warm closing line."},
    },
    "required": ["vibe", "topics", "moments", "people", "closing"],
    "additionalProperties": False,
}

PROFILE_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string", "description": "2-3 sentences on how this person communicates."},
        "sections": {"type": "array", "description": "Writing style; tone and humor; how they engage; "
                     "topics they bring; what they bring to the chat.", "items": {
            "type": "object", "properties": {"title": {"type": "string"},
                                             "points": {"type": "array", "items": {"type": "string"}}},
            "required": ["title", "points"], "additionalProperties": False}},
        "tips": {"type": "array", "description": "3-5 tips for chatting well with this person.",
                 "items": {"type": "string"}},
        "confidence": {"type": "string", "description": "How much data this is based on and what it can't tell."},
    },
    "required": ["summary", "sections", "tips", "confidence"],
    "additionalProperties": False,
}


class AIError(RuntimeError):
    pass


@dataclass
class Aliases:
    """Maps real names to 'Person A', 'Person B'... and back."""
    forward: dict[str, str]

    @classmethod
    def build(cls, names: list[str]) -> "Aliases":
        letters = list(string.ascii_uppercase) + [f"{a}{b}" for a in string.ascii_uppercase for b in string.ascii_uppercase]
        return cls({n: f"Person {letters[i]}" for i, n in enumerate(names)})

    def hide(self, text: str) -> str:
        """Mask phones, emails and links, then names."""
        return self.hide_names(URL.sub("[link]", EMAIL.sub("[email]", PHONE.sub("[phone]", text))))

    def hide_names(self, text: str) -> str:
        # full names first, then first names (only if unambiguous and not too short)
        firsts = {}
        for real in self.forward:
            first = real.split()[0]
            if len(first) >= 3:
                firsts.setdefault(first, []).append(real)
        for real, alias in sorted(self.forward.items(), key=lambda kv: -len(kv[0])):
            text = re.sub(rf"(?<!\w){re.escape(real)}(?!\w)", alias, text, flags=re.I)
        for first, reals in firsts.items():
            if len(reals) == 1:
                text = re.sub(rf"(?<!\w){re.escape(first)}(?!\w)", self.forward[reals[0]], text, flags=re.I)
        return text

    def reveal(self, value):
        if isinstance(value, str):
            for real, alias in sorted(self.forward.items(), key=lambda kv: -len(kv[1])):
                value = value.replace(alias, real)
            return value
        if isinstance(value, list):
            return [self.reveal(v) for v in value]
        if isinstance(value, dict):
            return {k: self.reveal(v) for k, v in value.items()}
        return value


def transcript(messages: list[Message], budget_chars: int, aliases: Aliases | None) -> tuple[str, int]:
    """Most recent messages that fit the budget, oldest first. Returns (text, how many were included)."""
    lines, used = [], 0
    for m in reversed(messages):
        body = {"media": "<media>", "deleted": "<deleted>"}.get(m.kind, m.text)
        sender = aliases.forward.get(m.sender, m.sender) if aliases else m.sender
        if aliases:
            body = aliases.hide(body)
        line = f"{m.ts:%Y-%m-%d %H:%M} | {sender}: {body}"
        if used + len(line) > budget_chars and lines:
            break
        lines.append(line)
        used += len(line) + 1
    lines.reverse()
    return "\n".join(lines), len(lines)


def _stats_brief(stats: ChatStats, aliases: Aliases | None) -> str:
    data = stats.to_dict()
    data.pop("heatmap_weekday_hour")
    data.pop("monthly")
    text = json.dumps(data, ensure_ascii=False, default=str)
    return aliases.hide_names(text) if aliases else text


def _call_claude(model: str, system: str, prompt: str, schema: dict, effort: str) -> dict:
    try:
        import anthropic
    except ImportError as e:
        raise AIError("Claude needs the anthropic package: pip install 'wca[claude]'") from e
    client = anthropic.Anthropic()  # ANTHROPIC_API_KEY or an `ant auth login` profile
    try:
        # Streaming keeps long inputs clear of HTTP timeouts. Server-side fallbacks re-run the request
        # on another model if the first one declines it.
        with client.beta.messages.stream(
            model=model,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        ) as stream:
            message = stream.get_final_message()
    except (anthropic.AuthenticationError, TypeError) as e:  # TypeError: no credentials configured at all
        raise AIError("Claude: invalid or missing API key (set ANTHROPIC_API_KEY)") from e
    except anthropic.RateLimitError as e:
        raise AIError("Claude: rate limited, try again in a minute") from e
    except anthropic.APIStatusError as e:
        raise AIError(f"Claude API error {e.status_code}: {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise AIError("Claude: network error, check your connection") from e
    if message.stop_reason == "refusal":
        raise AIError("Claude declined to analyze this chat")
    if message.stop_reason == "max_tokens":
        raise AIError("Claude's answer was cut off; try a smaller --budget")
    text = next((b.text for b in message.content if b.type == "text"), "")
    return json.loads(text)


def _call_openai(model: str, system: str, prompt: str, schema: dict, name: str) -> dict:
    try:
        import openai
    except ImportError as e:
        raise AIError("OpenAI needs the openai package: pip install 'wca[openai]'") from e
    client = openai.OpenAI()  # OPENAI_API_KEY
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            response_format={"type": "json_schema", "json_schema": {"name": name, "schema": schema, "strict": True}},
        )
    except openai.AuthenticationError as e:
        raise AIError("OpenAI: invalid or missing API key (set OPENAI_API_KEY)") from e
    except openai.APIStatusError as e:
        raise AIError(f"OpenAI API error {e.status_code}: {e.message}") from e
    except openai.APIConnectionError as e:
        raise AIError("OpenAI: network error, check your connection") from e
    choice = response.choices[0]
    if getattr(choice.message, "refusal", None):
        raise AIError(f"OpenAI declined: {choice.message.refusal}")
    return json.loads(choice.message.content)


def _run(provider: str, model: str | None, system: str, prompt: str, schema: dict, name: str, effort: str) -> dict:
    model = model or DEFAULT_MODELS[provider]
    if provider == "claude":
        return _call_claude(model, system, prompt, schema, effort)
    if provider == "openai":
        return _call_openai(model, system, prompt, schema, name)
    raise AIError(f"Unknown provider '{provider}'")


def _prompt(task: str, stats: ChatStats, messages: list[Message], budget: int, aliases: Aliases | None,
            language: str | None) -> str:
    text, included = transcript(messages, budget, aliases)
    note = "" if included == len(messages) else (
        f"(Only the most recent {included:,} of {len(messages):,} messages fit; the stats cover all of them.)\n")
    lang = f"Write in {language}." if language else (
        "Write in the language most messages are written in (judge from the message text, not from names).")
    return (f"{task}\n{lang}\n\n<stats>\n{_stats_brief(stats, aliases)}\n</stats>\n\n"
            f"<transcript>\n{note}{text}\n</transcript>")


def wrapped(stats: ChatStats, messages: list[Message], provider: str, model: str | None = None,
            budget: int = 150_000, anonymize: bool = False, language: str | None = None,
            effort: str = "medium") -> dict:
    aliases = Aliases.build([p.name for p in stats.people]) if anonymize else None
    prompt = _prompt("Write the Wrapped recap of this chat.", stats, messages, budget, aliases, language)
    result = _run(provider, model, WRAPPED_SYSTEM, prompt, WRAPPED_SCHEMA, "chat_wrapped", effort)
    return aliases.reveal(result) if aliases else result


def profile(person: str, stats: ChatStats, messages: list[Message], provider: str, model: str | None = None,
            budget: int = 150_000, anonymize: bool = False, language: str | None = None,
            effort: str = "medium") -> dict:
    aliases = Aliases.build([p.name for p in stats.people]) if anonymize else None
    who = aliases.forward[person] if aliases else person
    prompt = _prompt(f"Describe the communication style of {who}. Use the other participants' messages only "
                     f"as context for how {who} interacts.", stats, messages, budget, aliases, language)
    result = _run(provider, model, PROFILE_SYSTEM, prompt, PROFILE_SCHEMA, "communication_profile", effort)
    return aliases.reveal(result) if aliases else result
