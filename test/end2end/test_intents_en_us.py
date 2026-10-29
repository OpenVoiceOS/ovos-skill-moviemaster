"""End-to-end intent-routing tests for ovos-skill-moviemaster (en-US).

Boots an in-process MiniCroft with the skill loaded and feeds it real
utterances, asserting that each one routes to the expected ``.intent``
handler. The TMDB backend is never reached: routing is asserted on the
``{skill_id}:{intent}`` bus message, which fires before the handler runs, so
the suite stays offline.
"""
from unittest import TestCase

from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import CaptureSession
from ovoscope.routing import PIPELINE, TALLY, get_prototype_minicroft

SKILL_ID = "ovos-skill-moviemaster.openvoiceos"
LANG = "en-US"


class _RoutingTest(TestCase):
    """Shared MiniCroft harness for intent routing."""

    @classmethod
    def setUpClass(cls):
        cls.minicroft = get_prototype_minicroft([SKILL_ID], lang=LANG)

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "minicroft", None):
            cls.minicroft.stop()

    def _types(self, utterance):
        session = Session(f"e2e-en_us-{abs(hash(utterance))}")
        session.lang = LANG
        session.pipeline = PIPELINE
        message = Message(
            "recognizer_loop:utterance",
            {"utterances": [utterance], "lang": LANG},
            {"session": session.serialize()},
        )
        capture = CaptureSession(self.minicroft,
                                 eof_msgs=["mycroft.skill.handler.start"])
        capture.capture(message, timeout=30)
        return [m.msg_type for m in capture.finish()]

    def _assert_intent(self, utterance, intent_file):
        TALLY.assert_routed(utterance, f"{SKILL_ID}:{intent_file}",
                            self._types(utterance))

    def _assert_not_claimed_by(self, utterance, wrong_intent_file):
        TALLY.assert_not_routed(utterance, [f"{SKILL_ID}:{wrong_intent_file}"],
                                self._types(utterance))


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

    def test_show_me_genre_movies_ood_phrasing(self):
        self._assert_intent(
            "show me some thriller movies", "movie_genre_search.intent")

    def test_suggest_genre_movie_ood_phrasing(self):
        self._assert_intent(
            "suggest a fantasy movie", "movie_genre_search.intent")

    def test_suggest_genre_movies_ood_phrasing(self):
        self._assert_intent(
            "suggest sci-fi movies", "movie_genre_search.intent")


class TestMovieCastSiblingConfusion(_RoutingTest):
    """movie_cast.intent must not lose ground to movie_genre_search.intent.

    "list the cast of the movie X" and "list {genre} movies" share the
    (list|find|...) verb group -- movie_cast.intent's dedicated cast-listing
    line must win.
    """

    def test_list_the_cast_not_claimed_by_genre_search(self):
        self._assert_not_claimed_by(
            "list the cast of the movie Titanic", "movie_genre_search.intent")


class TestMovieDescriptionSiblingConfusion(_RoutingTest):
    """movie_description.intent must not steal recommendation requests."""

    def test_recommend_a_movie_not_claimed_by_description(self):
        self._assert_not_claimed_by(
            "recommend a movie like Inception", "movie_description.intent")


class TestMoviePopularSiblingConfusion(_RoutingTest):
    """movie_popular.intent must not lose "show ... popular movies" to
    movie_genre_search.intent's open {genre} slot."""

    def test_show_me_popular_movies_not_claimed_by_genre_search(self):
        self._assert_not_claimed_by(
            "show me popular movies", "movie_genre_search.intent")


class TestGenreTvSearch(_RoutingTest):
    """genre_tv_search.intent"""

    def test_find_genre_tv_shows(self):
        self._assert_intent("find comedy tv shows", "genre_tv_search.intent")

    def test_list_genre_television_shows(self):
        self._assert_intent(
            "list horror television shows", "genre_tv_search.intent")

    def test_get_genre_shows(self):
        self._assert_intent("get action shows", "genre_tv_search.intent")

    def test_i_want_to_watch_genre_ood_phrasing(self):
        self._assert_intent(
            "i want to watch a documentary", "genre_tv_search.intent")

    def test_show_me_genre_shows_ood_phrasing(self):
        self._assert_intent(
            "show me some drama series", "genre_tv_search.intent")

    def test_movie_genre_search_sibling_not_claimed(self):
        # "movies" (not "tv shows") is the movie_genre_search.intent sample
        # set -- genre_tv_search.intent must not steal it.
        self._assert_not_claimed_by(
            "find comedy movies", "genre_tv_search.intent")


class TestMovieRecommendationsSiblingNotClaimed(_RoutingTest):
    """"recommend" utterances must stay with movie_recommendations.intent
    and not be pulled into movie_genre_search.intent."""

    def test_recommend_similar_movies_not_claimed_by_genre_search(self):
        self._assert_not_claimed_by(
            "recommend movies like inception", "movie_genre_search.intent")
