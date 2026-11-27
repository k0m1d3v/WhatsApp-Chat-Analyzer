from datetime import datetime

from wca.parser import parse

IOS = """\
[25/12/23, 21:04:11] Friends: ‎Messages and calls are end-to-end encrypted.
[25/12/23, 21:04:11] Alice: Merry Christmas! 🎄
[25/12/23, 21:05:02] Bob: Thanks!
this is still Bob's message
[25/12/23, 21:06:00] Alice: ‎image omitted
[26/12/23, 09:00:00] Bob: This message was deleted
[26/12/23, 09:01:00] Alice: edited text <This message was edited>
"""

ANDROID_US = """\
12/25/23, 9:04 PM - Messages and calls are end-to-end encrypted. Tap to learn more.
12/25/23, 9:04 PM - Alice: Merry Christmas
12/25/23, 9:05 PM - Bob: <Media omitted>
1/2/24, 12:30 AM - Alice: late night
"""

ANDROID_IT = """\
25/12/2023, 21:04 - Alice: Buon Natale
25/12/2023, 21:05 - Bob: <Media omessi>
26/12/2023, 08:00 - Alice ha creato il gruppo "Famiglia"
"""


def test_ios_format():
    msgs = parse(IOS)
    assert [m.sender for m in msgs] == ["Alice", "Bob", "Alice", "Bob", "Alice"]
    assert msgs[0].ts == datetime(2023, 12, 25, 21, 4, 11)
    assert msgs[1].text == "Thanks!\nthis is still Bob's message"
    assert msgs[2].kind == "media"
    assert msgs[3].kind == "deleted"
    assert msgs[4].text == "edited text"


def test_android_us_12h_month_first():
    msgs = parse(ANDROID_US)
    assert len(msgs) == 3
    assert msgs[0].ts == datetime(2023, 12, 25, 21, 4)
    assert msgs[1].kind == "media"
    assert msgs[2].ts == datetime(2024, 1, 2, 0, 30)


def test_android_italian_4_digit_year():
    msgs = parse(ANDROID_IT)
    assert len(msgs) == 2  # the "created group" system line has no sender
    assert msgs[0].ts == datetime(2023, 12, 25, 21, 4)
    assert msgs[1].kind == "media"


def test_explicit_date_order():
    msgs = parse("[01/02/24, 10:00:00] A: hi\n", date_order="mdy")
    assert msgs[0].ts == datetime(2024, 1, 2, 10, 0)
