"""Regression test for the hardcoded TMDb API key leak.

The skill used to ship a live TMDb v3 API key as the default value for the
``apiv3`` setting, and every intent handler made a doomed live TMDb call
when no key was configured (tmdbv3api stringifies ``None`` to the literal
"None", which slips past its own empty-key guard). This asserts:

  * no plausible hardcoded API key remains in source
  * the keyless intent path never touches ``tmdbv3api`` (no network object
    constructed) and speaks the "no_valid_api" dialog instead of raising
"""
import importlib.util
import os
import re
import unittest
from unittest.mock import patch

REPO = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
INIT_PY = os.path.join(REPO, "__init__.py")


def _load_skill_module():
    spec = importlib.util.spec_from_file_location("moviemaster_init", INIT_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestNoHardcodedApiKey(unittest.TestCase):
    def test_no_hex_default_for_apiv3_setting(self):
        with open(INIT_PY) as f:
            source = f.read()
        # 'apiv3' default must not be a 32-char hex string (a plausible API key)
        match = re.search(r'"apiv3":\s*self\.settings\.get\("apiv3",\s*"([^"]*)"\)', source)
        self.assertIsNotNone(match, "could not locate apiv3 default in source")
        default_value = match.group(1)
        self.assertFalse(
            re.fullmatch(r"[0-9a-f]{32}", default_value or ""),
            f"apiv3 default {default_value!r} looks like a hardcoded API key")

    def test_no_32char_hex_literal_anywhere_in_source(self):
        # Catches any hardcoded-looking key string, not just the specific
        # leaked one, without ever writing a real/former secret into the
        # test file itself.
        with open(INIT_PY) as f:
            source = f.read()
        hits = re.findall(r'"[0-9a-f]{32}"', source)
        self.assertEqual(hits, [], f"found plausible hardcoded key literal(s): {hits}")


class TestKeylessIntentPathNeverTouchesNetwork(unittest.TestCase):
    """Proves the fix: with no api_key, intent handlers must not construct
    any tmdbv3api object (i.e. no network interaction), and must speak
    no_valid_api instead of raising.

    Sanity-checked RED against the unfixed state (see PR description):
    reverting the guards in __init__.py while keeping this test makes
    test_search_for_movie_speaks_dialog_without_network_call FAIL, because
    Movie() (mocked here) gets constructed/called before any dialog is
    spoken.
    """

    def setUp(self):
        from ovos_workshop.skills import OVOSSkill  # noqa: F401
        self.module = _load_skill_module()

        self.skill = self.module.MovieMaster.__new__(self.module.MovieMaster)
        self.skill._api_key = None
        self.skill._search_depth = 5
        self.skill._match_confidence = 0.8
        self.skill._active_movie = None
        self.skill._active_person = None
        self.spoken = []
        self.skill.speak_dialog = lambda dialog, data=None: self.spoken.append(dialog)

    def test_search_for_movie_speaks_dialog_without_network_call(self):
        with patch.object(self.module, "Movie") as mock_movie, \
             patch.object(self.module, "TMDb") as mock_tmdb:
            self.skill._search_for_movie("Blade Runner")

        mock_movie.assert_not_called()
        mock_tmdb.assert_not_called()
        self.assertIn("no_valid_api", self.spoken)

    def test_search_for_person_speaks_dialog_without_network_call(self):
        with patch.object(self.module, "Person") as mock_person, \
             patch.object(self.module, "TMDb") as mock_tmdb:
            self.skill._search_for_person("Ridley Scott")

        mock_person.assert_not_called()
        mock_tmdb.assert_not_called()
        self.assertIn("no_valid_api", self.spoken)

    def test_match_genre_speaks_dialog_without_network_call(self):
        with patch.object(self.module, "Genre") as mock_genre, \
             patch.object(self.module, "TMDb") as mock_tmdb:
            result = self.skill._match_genre("action")

        mock_genre.assert_not_called()
        mock_tmdb.assert_not_called()
        self.assertIsNone(result)
        self.assertIn("no_valid_api", self.spoken)

    def test_discover_by_genre_speaks_dialog_without_network_call(self):
        with patch.object(self.module, "Discover") as mock_discover, \
             patch.object(self.module, "TMDb") as mock_tmdb:
            result = self.skill._discover_by_genre(28)

        mock_discover.assert_not_called()
        mock_tmdb.assert_not_called()
        self.assertEqual(result, [])
        self.assertIn("no_valid_api", self.spoken)

    def test_handle_popular_movies_speaks_dialog_without_network_call(self):
        message = type("Msg", (), {"data": {}})()
        with patch.object(self.module, "Movie") as mock_movie:
            self.skill.handle_popular_movies(message)

        mock_movie.assert_not_called()
        self.assertIn("no_valid_api", self.spoken)

    def test_handle_top_movies_speaks_dialog_without_network_call(self):
        message = type("Msg", (), {"data": {}})()
        with patch.object(self.module, "Movie") as mock_movie:
            self.skill.handle_top_movies(message)

        mock_movie.assert_not_called()
        self.assertIn("no_valid_api", self.spoken)


class TestStaleActiveStateClearedOnKeylessSearch(unittest.TestCase):
    """A previously-configured key can be removed at runtime (settings
    change). If a stale ``_active_movie``/``_active_person`` survives that,
    handlers like ``handle_movie_cast``/``handle_movie_length`` still see a
    truthy ``active_movie`` and fire real TMDb calls (or speak a stale
    answer) even though the key is now gone. ``_search_for_movie``/
    ``_search_for_person`` must clear that stale state before returning on
    the keyless path.
    """

    def setUp(self):
        from ovos_workshop.skills import OVOSSkill  # noqa: F401
        self.module = _load_skill_module()

        self.skill = self.module.MovieMaster.__new__(self.module.MovieMaster)
        self.skill._api_key = None
        self.skill._search_depth = 5
        self.skill._match_confidence = 0.8
        # Simulate a stale selection left over from when a key existed.
        stale_movie = type("StaleMovie", (), {"id": 1, "title": "Stale Movie",
                                                "release_date": "1982-06-25"})()
        self.skill._active_movie = stale_movie
        self.skill._active_person = None
        self.spoken = []
        self.skill.speak_dialog = lambda dialog, data=None: self.spoken.append(dialog)

    def test_search_for_movie_clears_stale_active_movie(self):
        with patch.object(self.module, "Movie") as mock_movie, \
             patch.object(self.module, "TMDb") as mock_tmdb:
            self.skill._search_for_movie("New Movie")

        mock_movie.assert_not_called()
        mock_tmdb.assert_not_called()
        self.assertIn("no_valid_api", self.spoken)
        self.assertIsNone(self.skill.active_movie,
                           "stale active_movie must be cleared on the keyless path")

    def test_handle_movie_year_makes_no_network_call_and_no_stale_answer(self):
        # Follow-up handler call, as a user would trigger next. Before fix 2,
        # this saw the stale active_movie survive _search_for_movie's early
        # return and spoke a stale "movie_year" answer (from the old,
        # possibly wrong, selection) right after no_valid_api.
        message = type("Msg", (), {"data": {"movie": "New Movie"}})()
        with patch.object(self.module, "Movie") as mock_movie, \
             patch.object(self.module, "TMDb") as mock_tmdb:
            self.skill.handle_movie_year(message)

        mock_movie.assert_not_called()
        mock_tmdb.assert_not_called()
        self.assertIn("no_valid_api", self.spoken)
        self.assertNotIn("movie_year", self.spoken,
                          "must not speak a stale year answer with no api key")
        self.assertNotIn("movie_year_error", self.spoken)


class TestVerifyApiHandlesMissingKey(unittest.TestCase):
    def setUp(self):
        from ovos_workshop.skills import OVOSSkill  # noqa: F401
        self.module = _load_skill_module()
        self.skill = self.module.MovieMaster.__new__(self.module.MovieMaster)
        self.spoken = []
        self.skill.speak_dialog = lambda dialog, data=None: self.spoken.append(dialog)

    def test_verify_api_returns_none_and_speaks_dialog_without_network_call(self):
        with patch.object(self.module, "Movie") as mock_movie, \
             patch.object(self.module, "TMDb") as mock_tmdb:
            result = self.skill.verify_api("")

        mock_movie.assert_not_called()
        mock_tmdb.assert_not_called()
        self.assertIsNone(result)
        self.assertIn("no_valid_api", self.spoken)

        self.spoken.clear()
        with patch.object(self.module, "Movie") as mock_movie, \
             patch.object(self.module, "TMDb") as mock_tmdb:
            result = self.skill.verify_api(None)

        mock_movie.assert_not_called()
        mock_tmdb.assert_not_called()
        self.assertIsNone(result)
        self.assertIn("no_valid_api", self.spoken)


if __name__ == "__main__":
    unittest.main()
