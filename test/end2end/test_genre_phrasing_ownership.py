"""A bare genre goes to television; a genre with a movie noun does not.

`genre_tv_search.intent` gained two things: `series` as a television noun,
and a template for a genre with no noun at all ("i want to watch a
documentary"). The second one is a prefix of `movie_genre_search.intent`'s
"i want to watch [a|some] {genre} (movie|movies|film|films|flicks)", so the
two intents share most of their words.

The movie intent must keep its own phrasings. This module asserts both
directions, so a change that moves every movie request to television fails
here.
"""
import pytest
from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovos_spec_tools import canonical_intent_topic
from ovoscope import CaptureSession
from ovoscope.routing import PIPELINE, TALLY, get_prototype_minicroft

SKILL_ID = "ovos-skill-moviemaster.openvoiceos"
LANG = "en-US"
TV = f"{SKILL_ID}:genre_tv_search"
MOVIE = f"{SKILL_ID}:movie_genre_search"


@pytest.fixture(scope="module")
def minicroft():
    mc = get_prototype_minicroft([SKILL_ID], lang=LANG)
    yield mc
    mc.stop()


def _fire(mc, utterance):
    session = Session(f"genre-ownership-{abs(hash(utterance))}")
    session.lang = LANG
    session.pipeline = PIPELINE
    message = Message(
        "recognizer_loop:utterance",
        {"utterances": [utterance], "lang": LANG},
        {"session": session.serialize()},
    )
    capture = CaptureSession(mc, eof_msgs=["mycroft.skill.handler.start"])
    capture.capture(message, timeout=30)
    return capture.finish()


@pytest.mark.parametrize("utterance", [
    "i want to watch a documentary",
    "show me some drama series",
    "list horror series",
    "list horror television shows",
])
def test_television_phrasings_go_to_the_television_intent(minicroft, utterance):
    types = [m.msg_type for m in _fire(minicroft, utterance)]
    TALLY.assert_routed(utterance, TV, types)


@pytest.mark.parametrize("utterance", [
    "i want to watch a documentary film",
    "i want to watch a comedy movie",
    "find action movies",
    "show me some thriller films",
])
def test_movie_phrasings_still_go_to_a_movie_intent(minicroft, utterance):
    """The control that matters: the bare-genre template steals nothing."""
    types = [m.msg_type for m in _fire(minicroft, utterance)]
    TALLY.assert_routed(utterance, MOVIE, types)


def test_the_genre_slot_is_filled_not_just_matched(minicroft):
    """A match that binds no slot would answer about no genre at all."""
    utterance = "i want to watch a documentary"
    messages = _fire(minicroft, utterance)
    TALLY.assert_routed(utterance, TV, [m.msg_type for m in messages])
    matched = next(m for m in messages
                   if canonical_intent_topic(m.msg_type) == TV)
    assert matched.data.get("genre") == "documentary", matched.data


def test_an_unrelated_utterance_is_claimed_by_neither(minicroft):
    """The control on the control: the skill does not claim everything."""
    utterance = "what is the weather tomorrow"
    types = [m.msg_type for m in _fire(minicroft, utterance)]
    TALLY.assert_not_routed(utterance, [TV, MOVIE], types)
