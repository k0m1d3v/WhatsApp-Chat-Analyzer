"""AI flow and HTML report, with the model call replaced by a fake (no network, no cost)."""
from pathlib import Path

from wca import ai, report
from wca.cli import main
from wca.parser import load
from wca.stats import compute

SAMPLE = Path(__file__).parent.parent / "examples" / "sample_chat.txt"


def fake_run(captured):
    def run(provider, model, system, prompt, schema, name, effort):
        captured.update(provider=provider, prompt=prompt, schema=schema)
        if name == "chat_wrapped":
            return {"vibe": "Pizza first <script>alert(1)</script>", "topics": [{"title": "Pizza", "description": "Person A"}],
                    "moments": [{"date": "2024-01-30", "description": "the busiest day"}],
                    "people": [{"name": "Person A", "description": "the energy of the chat"}], "closing": "bye"}
        return {"summary": "Person C writes long, thoughtful messages.", "sections": [{"title": "Style", "points": ["long"]}],
                "tips": ["give Person C time"], "confidence": "based on 334 messages"}
    return run


def test_wrapped_anonymized(monkeypatch):
    captured = {}
    monkeypatch.setattr(ai, "_run", fake_run(captured))
    msgs = load(SAMPLE)
    s = compute(msgs)
    r = ai.wrapped(s, msgs, provider="claude", anonymize=True, budget=5_000)
    sent = captured["prompt"]
    assert all(name not in sent for name in ("Giulia", "Marco", "Sara"))      # names never leave
    assert "Only the most recent" in sent                                     # budget respected and declared
    assert r["people"][0]["name"] == "Giulia"                                 # aliases mapped back locally
    html = report.render(s, "Test", ai_wrapped=r)
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;" in html


def test_profile_cli(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr(ai, "_run", fake_run(captured))
    out = tmp_path / "p.html"
    code = main(["profile", str(SAMPLE), "--person", "Sara", "--ai", "openai", "--anonymize", "--yes",
                 "--html", str(out), "--json", str(tmp_path / "p.json")])
    assert code == 0
    assert "Person C" in captured["prompt"] and "Sara" not in captured["prompt"]
    page = out.read_text(encoding="utf-8")
    assert "How Sara communicates" in page and "Sara writes long" in page
