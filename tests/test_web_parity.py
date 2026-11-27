"""The browser version (site/js) must give the same numbers as the Python package."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from wca.parser import load
from wca.stats import compute

ROOT = Path(__file__).parent.parent
CHATS = [ROOT / "examples" / "sample_chat.txt", ROOT / "tests" / "fixtures" / "android_it_12h.txt"]


@pytest.mark.skipif(not shutil.which("node"), reason="Node.js not installed")
@pytest.mark.parametrize("chat", CHATS, ids=lambda p: p.name)
def test_js_matches_python(chat):
    out = subprocess.run(["node", str(ROOT / "tests" / "web_stats.mjs"), str(chat)],
                         capture_output=True, text=True, encoding="utf-8", check=True).stdout
    js = json.loads(out)
    s = compute(load(chat))
    assert js["total_messages"] == s.total_messages
    assert js["total_words"] == s.total_words
    assert js["active_days"] == s.active_days
    assert js["conversations"] == s.conversations
    assert js["longest_streak"] == s.longest_streak[0]
    assert js["busiest_day"] == s.busiest_day[1]
    assert js["heatmap"] == s.heatmap
    assert [tuple(w) for w in js["top_words"]] == s.top_words
    assert [tuple(e) for e in js["top_emojis"]] == s.top_emojis
    for jp, p in zip(js["people"], s.people):
        assert (jp["name"], jp["messages"], jp["words"], jp["media"], jp["deleted"], jp["emojis"], jp["laughs"],
                jp["questions"], jp["starts"], jp["night"], jp["replies"]) == (
            p.name, p.messages, p.words, p.media, p.deleted, p.emojis, p.laughs,
            p.questions, p.conversation_starts, p.night_messages, len(p.reply_seconds))
        assert jp["median_reply"] == pytest.approx(p.median_reply_minutes)
    assert [tuple(a) for a in js["awards"]] == [(a.title, a.winner) for a in s.awards]


@pytest.mark.skipif(not shutil.which("node"), reason="Node.js not installed")
def test_web_smoke():
    """Zip reading, AI request shapes, anonymization and escaping in the browser code (fetch is faked)."""
    subprocess.run(["node", str(ROOT / "tests" / "web_smoke.mjs")], check=True)
