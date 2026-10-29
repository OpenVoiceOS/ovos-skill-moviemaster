"""Slot-extraction end-to-end coverage for ovos-skill-moviemaster (en-US).

Routing to the right ``.intent`` file is necessary but not sufficient: the
handler also needs the ``{movie}``/``{genre}`` slot value extracted from the
utterance. This suite fires real utterances through a MiniCroft and asserts
on the slot value carried by the matched bus message, not just its type.
"""
import pytest
from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovos_spec_tools import canonical_intent_topic
from ovoscope import CaptureSession
from ovoscope.routing import PIPELINE, TALLY, get_prototype_minicroft

SKILL_ID = "ovos-skill-moviemaster.openvoiceos"
LANG = "en-US"

# (utterance, intent basename, slot name, expected slot value)
SLOT_CASES = [
    ("what's the movie Titanic about", "movie_description", "movie", "titanic"),
    ("describe the movie Jaws", "movie_description", "movie", "jaws"),
    ("when did the movie Titanic come out", "movie_year", "movie", "titanic"),
    ("what year did the film Jaws come out", "movie_year", "movie", "jaws"),
    ("who's in the movie inception", "movie_cast", "movie", "inception"),
    ("who stars in the movie The Godfather", "movie_cast", "movie", "the godfather"),
    ("list the cast of the movie Titanic", "movie_cast", "movie", "titanic"),
    ("what genre is the film Titanic", "movie_genres", "movie", "titanic"),
    ("what kind of movie is the movie Alien", "movie_genres", "movie", "alien"),
    ("find action movies", "movie_genre_search", "genre", "action"),
    ("show me some thriller movies", "movie_genre_search", "genre", "thriller"),
    ("find comedy tv shows", "genre_tv_search", "genre", "comedy"),
    ("show me horror television shows", "genre_tv_search", "genre", "horror"),
    ("how long is the movie Titanic", "movie_runtime", "movie", "titanic"),
    ("how many minutes is the movie Alien", "movie_runtime", "movie", "alien"),
    ("recommend a movie like Inception", "movie_recommendations", "movie", "inception"),
    ("suggest movies similar to Jaws", "movie_recommendations", "movie", "jaws"),
    ("what should I watch if I liked Titanic", "movie_recommendations", "movie", "titanic"),
]


@pytest.fixture(scope="module")
def minicroft():
    mc = get_prototype_minicroft([SKILL_ID], lang=LANG)
    yield mc
    mc.stop()


def _fire(mc, text, session_id):
    session = Session(session_id)
    session.lang = LANG
    session.pipeline = PIPELINE
    message = Message(
        "recognizer_loop:utterance",
        {"utterances": [text], "lang": LANG},
        {"session": session.serialize()},
    )
    capture = CaptureSession(mc, eof_msgs=["mycroft.skill.handler.start"])
    capture.capture(message, timeout=30)
    return capture.finish()


@pytest.mark.parametrize("case", SLOT_CASES, ids=lambda c: c[0])
def test_slot_value_extracted(minicroft, case):
    utterance, intent_base, slot, expected = case
    expected_type = f"{SKILL_ID}:{intent_base}"
    messages = _fire(minicroft, utterance, f"slot-{utterance}")
    TALLY.assert_routed(utterance, expected_type, [m.msg_type for m in messages])
    messages = [m for m in messages
                if canonical_intent_topic(m.msg_type) == expected_type]
    got = messages[0].data.get(slot)
    assert got is not None, (
        f"{utterance!r} matched {intent_base}.intent but slot {slot!r} was not "
        f"extracted (message data: {messages[0].data!r})"
    )
    assert got.lower().strip() == expected, (
        f"{utterance!r}: expected {slot}={expected!r}, got {got!r}"
    )
