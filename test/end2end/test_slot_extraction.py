"""Slot-extraction end-to-end coverage for ovos-skill-moviemaster (en-US).

Routing to the right ``.intent`` file is necessary but not sufficient: the
handler also needs the ``{movie}``/{genre}`` slot value padatious extracted
from the utterance. This suite fires real utterances through the same
MiniCroft/padatious pipeline as ``test_golden_utterances.py`` and asserts on
the slot value carried by the matched bus message, not just its type.
"""
import time

import pytest
from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import get_minicroft

SKILL_ID = "ovos-skill-moviemaster.openvoiceos"
LANG = "en-US"

PIPELINE = [
    "ovos-padatious-pipeline-plugin-high",
    "ovos-padatious-pipeline-plugin-medium",
    "ovos-padatious-pipeline-plugin-low",
]

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
    mc = get_minicroft([SKILL_ID])
    yield mc
    mc.stop()


def _fire(mc, text, session_id, listen_types, timeout=30):
    captured = []
    handler = lambda msg: captured.append(msg)
    for msg_type in listen_types:
        mc.bus.on(msg_type, handler)
    try:
        session = Session(session_id)
        session.lang = LANG
        session.pipeline = list(PIPELINE)
        mc.bus.emit(Message(
            "recognizer_loop:utterance",
            {"utterances": [text], "lang": LANG},
            {"session": session.serialize()},
        ))
        deadline = time.monotonic() + timeout
        while not captured and time.monotonic() < deadline:
            time.sleep(0.2)
    finally:
        for msg_type in listen_types:
            mc.bus.remove(msg_type, handler)
    return captured


@pytest.mark.parametrize("case", SLOT_CASES, ids=lambda c: c[0])
def test_slot_value_extracted(minicroft, case):
    utterance, intent_base, slot, expected = case
    candidates = {f"{SKILL_ID}:{intent_base}", f"{SKILL_ID}:{intent_base}.intent"}
    messages = _fire(minicroft, utterance, f"slot-{utterance}", candidates)
    assert messages, f"{utterance!r} did not route to {intent_base}.intent"
    got = messages[0].data.get(slot)
    assert got is not None, (
        f"{utterance!r} matched {intent_base}.intent but slot {slot!r} was not "
        f"extracted (message data: {messages[0].data!r})"
    )
    assert got.lower().strip() == expected, (
        f"{utterance!r}: expected {slot}={expected!r}, got {got!r}"
    )
