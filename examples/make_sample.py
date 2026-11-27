"""Generate examples/sample_chat.txt: a fictional 3-person chat to try the tool on.

    python examples/make_sample.py
"""
import random
from datetime import datetime, timedelta
from pathlib import Path

random.seed(7)
PEOPLE = {
    # name: (weight, typical hour, words per message, emoji chance, reply speed in minutes)
    "Giulia": (5, 21, 9, 0.5, 2),
    "Marco": (3, 23, 4, 0.15, 12),
    "Sara": (2, 13, 16, 0.3, 30),
}
LINES = {
    "Giulia": ["who's up for pizza tonight?", "omg did you see the match", "I'm sooo tired today",
               "send me the photos from saturday!", "haha no way", "ok I'm on my way", "love you guys",
               "what time is the cinema?", "guess who I just met at the station", "hahaha I can't"],
    "Marco": ["lol", "yes", "on my way", "sure", "haha", "let me check", "can't tonight", "nice", "who's driving?",
              "pizza again?", "ok"],
    "Sara": ["I've been reading this book about the history of maps and honestly it's fascinating",
             "Just finished my shift, does anyone want to grab a coffee tomorrow morning before class?",
             "Reminder that we still need to book the house for the summer trip, prices are going up",
             "Here's the article I was talking about https://example.com/article",
             "Can we please decide the date for the trip this week? I made a list:\n- July 3-10\n- July 17-24",
             "That's hilarious 😂 but also a bit worrying"],
}
EMOJIS = ["😂", "❤️", "🍕", "😭", "🔥", "👍", "🙈", "✨", "😴", "⚽"]


def main() -> None:
    t = datetime(2024, 1, 8, 9, 0)
    end = datetime(2024, 7, 28, 23, 0)
    lines = [f"[08/01/24, 09:00:00] Friends 🍕: ‎Messages and calls are end-to-end encrypted."]
    names, weights = list(PEOPLE), [PEOPLE[n][0] for n in PEOPLE]
    prev = None
    while t < end:
        # a conversation: a burst of messages, then a silence
        hour = PEOPLE[random.choices(names, weights)[0]][1]
        t = t.replace(hour=max(7, min(23, int(random.gauss(hour, 2)))), minute=random.randrange(60))
        for _ in range(random.randint(3, 25)):
            who = random.choices(names, weights)[0]
            _, _, _, emoji_p, speed = PEOPLE[who]
            t += timedelta(minutes=random.expovariate(1 / speed) if who != prev else random.uniform(0.1, 1.5),
                           seconds=random.randrange(60))
            r = random.random()
            if r < 0.06:
                text = "‎image omitted"
            elif r < 0.075:
                text = "‎sticker omitted"
            elif r < 0.08:
                text = "This message was deleted"
            else:
                text = random.choice(LINES[who])
                if random.random() < emoji_p:
                    text += " " + random.choice(EMOJIS) * random.randint(1, 3)
            lines.append(f"[{t:%d/%m/%y, %H:%M:%S}] {who}: {text}")
            prev = who
        t += timedelta(hours=random.choice([5, 10, 20, 26, 30, 50, 75]))
    out = Path(__file__).with_name("sample_chat.txt")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(lines) - 1} messages -> {out}")


if __name__ == "__main__":
    main()
