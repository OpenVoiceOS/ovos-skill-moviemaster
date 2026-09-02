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
        # Different padatious/padacioso plugin versions register the
        # matched-intent bus event under different normalizations of the
        # ``.intent`` filename basename -- observed variants include the
        # bare basename with no extension and the basename with the
        # extension kept. Listen for both wire forms instead of pinning
        # one (which breaks the moment the matching plugin version
        # changes; see ovos-skill-personal#113 for the same drift).
        basename = intent_file.rsplit(".", 1)[0] if intent_file.endswith(".intent") else intent_file
        candidates = {f"{SKILL_ID}:{intent_file}", f"{SKILL_ID}:{basename}"}
        matched = []
        handler = lambda msg: matched.append(msg)
        for msg_type in candidates:
            self.bus.on(msg_type, handler)
        try:
            session = Session(f"e2e-en_us-{intent_file}-{abs(hash(utterance))}")
            session.lang = LANG
            session.pipeline = PIPELINE
            self.bus.emit(Message(
                "recognizer_loop:utterance",
                {"utterances": [utterance], "lang": LANG},
                {"session": session.serialize()},
            ))
            deadline = time.monotonic() + 30
            while not matched and time.monotonic() < deadline:
                time.sleep(0.2)
        finally:
            for msg_type in candidates:
                self.bus.remove(msg_type, handler)
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


class TestGenreTvSearch(_RoutingTest):
    """genre_tv_search.intent"""

    def test_find_genre_tv_shows(self):
        self._assert_intent("find comedy tv shows", "genre_tv_search.intent")

    def test_list_genre_television_shows(self):
        self._assert_intent(
            "list horror television shows", "genre_tv_search.intent")

    def test_get_genre_shows(self):
        self._assert_intent("get action shows", "genre_tv_search.intent")

    def test_movie_genre_search_sibling_not_claimed(self):
        # "movies" (not "tv shows") is the movie_genre_search.intent sample
        # set -- genre_tv_search.intent must not steal it. Listen for both
        # siblings so a genuine (correct) match on movie_genre_search.intent
        # lets the test exit early instead of idling the full timeout.
        tv_candidates = {
            f"{SKILL_ID}:genre_tv_search.intent", f"{SKILL_ID}:genre_tv_search"}
        movie_candidates = {
            f"{SKILL_ID}:movie_genre_search.intent",
            f"{SKILL_ID}:movie_genre_search",
        }
        all_candidates = tv_candidates | movie_candidates
        matched = []
        handler = lambda msg: matched.append(msg)
        for msg_type in all_candidates:
            self.bus.on(msg_type, handler)
        try:
            session = Session("e2e-en_us-genre_tv_search-sibling-negative")
            session.lang = LANG
            session.pipeline = PIPELINE
            self.bus.emit(Message(
                "recognizer_loop:utterance",
                {"utterances": ["find comedy movies"], "lang": LANG},
                {"session": session.serialize()},
            ))
            deadline = time.monotonic() + 30
            while not matched and time.monotonic() < deadline:
                time.sleep(0.2)
        finally:
            for msg_type in all_candidates:
                self.bus.remove(msg_type, handler)
        claimed_by_tv = [m for m in matched if m.msg_type in tv_candidates]
        self.assertFalse(
            claimed_by_tv,
            "'find comedy movies' (movie_genre_search.intent) was "
            "incorrectly claimed by genre_tv_search.intent",
        )
