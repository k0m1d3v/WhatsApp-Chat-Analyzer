from datetime import datetime, timedelta

from wca.ai import Aliases
from wca.parser import Message
from wca.stats import compute, filter_messages


def msg(minutes, sender, text="hello there", kind="text"):
    return Message(datetime(2024, 1, 1, 10, 0) + timedelta(minutes=minutes), sender, text, kind)


CHAT = [
    msg(0, "Alice", "hey how are you? 😂😂"),
    msg(2, "Bob", "good thanks"),
    msg(3, "Bob", "you?"),
    msg(10, "Alice", "great, haha"),
    msg(60 * 24, "Bob", "morning"),          # next day: new conversation started by Bob
    msg(60 * 24 + 1, "Alice", "", "media"),
    msg(60 * 24 * 5, "Alice", "anyone?"),   # 4-day silence, new conversation
]


def test_counts_and_conversations():
    s = compute(CHAT)
    alice, bob = s.person("Alice"), s.person("Bob")
    assert s.total_messages == 7
    assert alice.messages == 4 and bob.messages == 3
    assert s.conversations == 3
    assert alice.conversation_starts == 2 and bob.conversation_starts == 1
    assert alice.media == 1
    assert alice.emojis == 2
    assert alice.questions == 2


def test_reply_times_and_records():
    s = compute(CHAT)
    assert s.person("Bob").reply_seconds == [120.0]
    assert s.person("Alice").reply_seconds == [420.0, 60.0]
    assert s.longest_streak[0] == 2
    assert s.longest_silence[0] > timedelta(days=3)
    assert s.active_days == 3


def test_last_counts_back_from_last_message():
    kept = filter_messages(CHAT, last="2d")
    assert [m.text for m in kept] == ["anyone?"]


def test_aliases_hide_and_reveal():
    a = Aliases.build(["Alice Smith", "Bob"])
    hidden = a.hide("Alice said call Bob at +39 333 123 4567 or alice@mail.com, see https://x.io")
    assert "Alice" not in hidden and "Bob" not in hidden
    assert "[phone]" in hidden and "[email]" in hidden and "[link]" in hidden
    assert "2024-01-02" in a.hide("on 2024-01-02")  # dates are not phone numbers
    assert a.reveal({"x": ["Person A and Person B"]}) == {"x": ["Alice Smith and Bob"]}
