"""End-to-end intent-routing tests for ovos-skill-moviemaster (en-US).

Boots an in-process MiniCroft with the skill loaded and feeds it real
utterances through the padatious pipeline, asserting that each one routes to
the expected ``.intent`` handler. The TMDB backend is never reached: routing
is asserted on the ``{skill_id}:{intent}`` bus message, which fires before the
handler runs, so the suite is deterministic and offline.
"""
import time
from unittest import TestCase

from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import get_minicroft

SKILL_ID = "ovos-skill-moviemaster.openvoiceos"
LANG = "en-US"

# The intent files are padatious samples. Exact expansions score in the -high
# band while the slotted variants land lower, so register both bands.
PIPELINE = [
    "ovos-padatious-pipeline-plugin-high",
    "ovos-padatious-pipeline-plugin-medium",
    "ovos-padatious-pipeline-plugin-low",
]


class _RoutingTest(TestCase):
    """Shared MiniCroft harness for padatious intent routing."""

    @classmethod
    def setUpClass(cls):
        cls.minicroft = get_minicroft([SKILL_ID])
        cls.bus = cls.minicroft.bus

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "minicroft", None):
            cls.minicroft.stop()

    def _assert_intent(self, utterance, intent_file):
        intent_msg_type = f"{SKILL_ID}:{intent_file}"
        matched = []
        handler = lambda msg: matched.append(msg)
        self.bus.on(intent_msg_type, handler)
        try:
            session = Session(f"e2e-en_us-{intent_file}-{abs(hash(utterance))}")
            session.lang = LANG
            session.pipeline = PIPELINE
            self.bus.emit(Message(
                "recognizer_loop:utterance",
                {"utterances": [utterance], "lang": LANG},
                {"session": session.serialize()},
            ))
            deadline = time.monotonic() + 60
            while not matched and time.monotonic() < deadline:
                time.sleep(0.2)
        finally:
            self.bus.remove(intent_msg_type, handler)
        self.assertTrue(
            matched,
            f"{utterance!r} did not route to {intent_file}",
        )


class TestMovieCast(_RoutingTest):
    """movie_cast.intent"""

    def test_who_acts_in_the_movie(self):
        self._assert_intent("who acts in the movie inception", "movie_cast.intent")


class TestMovieYear(_RoutingTest):
    """movie_year.intent"""

    def test_what_year_was_the_movie_released(self):
        self._assert_intent(
            "what year was the movie the matrix released", "movie_year.intent")


class TestMovieGenreSearch(_RoutingTest):
    """movie_genre_search.intent"""

    def test_find_genre_movies(self):
        self._assert_intent("find action movies", "movie_genre_search.intent")
