"""Handlers when TMDb returns no matching title, and empty TMDb lists.

A question about an unknown title must not be answered with the data of the
previously asked movie, and an empty popular list must speak a dialog instead
of raising NameError.
"""
import importlib.util
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

REPO = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
INIT_PY = os.path.join(REPO, "__init__.py")

INCEPTION = SimpleNamespace(id=27205, title="Inception", overview="A thief.",
                            release_date="2010-07-16")


def _load_skill_module():
    spec = importlib.util.spec_from_file_location("moviemaster_init", INIT_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestUnmatchedSearch(unittest.TestCase):

    def setUp(self):
        self.module = _load_skill_module()
        self.skill = self.module.MovieMaster.__new__(self.module.MovieMaster)
        self.skill._api_key = "test-key-not-a-real-tmdb-key"
        self.skill._search_depth = 5
        self.skill._match_confidence = 0.8
        self.skill._active_movie = None
        self.skill._active_person = None
        self.skill._settings = {"match_confidence": 0.8}
        self.skill._configure_tmdb = lambda: None
        patcher = patch.object(
            self.module.MovieMaster, "lang", "en-US", create=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.spoken = []
        self.skill.speak_dialog = \
            lambda dialog, data=None: self.spoken.append((dialog, data))
        self.skill.speak = lambda text: self.spoken.append(("speak", text))

    def _ask(self, handler, movie, results):
        message = SimpleNamespace(data={"movie": movie})
        with patch.object(self.module, "Movie") as movie_cls, \
                patch.object(self.module, "TMDb"):
            movie_cls.return_value.search.return_value = results
            getattr(self.skill, handler)(message)

    def _known_then_unknown(self, handler):
        self._ask(handler, "Inception", [INCEPTION])
        self.assertEqual(self.skill.active_movie, INCEPTION)
        self.spoken.clear()
        self._ask(handler, "Zzyzx Quux", [])
        self.assertIsNone(self.skill.active_movie)

    def test_unknown_title_speaks_no_info_for_each_movie_handler(self):
        for handler in ("handle_movie_description_intent",
                        "handle_movie_year", "handle_movie_cast",
                        "handle_movie_genre", "handle_movie_length",
                        "handle_movie_recommendations"):
            with self.subTest(handler=handler):
                self.spoken.clear()
                self._known_then_unknown(handler)
                self.assertEqual(
                    self.spoken, [("no_info", {"movie": "Zzyzx Quux"})])

    def test_unknown_title_does_not_keep_previous_movie(self):
        self._known_then_unknown("handle_movie_year")
        self.assertNotIn("movie_year", [d for d, _ in self.spoken])

    def test_unmatched_person_search_clears_active_person(self):
        ridley = SimpleNamespace(name="Ridley Scott")
        with patch.object(self.module, "Person") as person_cls, \
                patch.object(self.module, "TMDb"):
            person_cls.return_value.search.return_value = [ridley]
            self.skill._search_for_person("Ridley Scott")
            self.assertEqual(self.skill.active_person, ridley)
            person_cls.return_value.search.return_value = []
            self.skill._search_for_person("Zzyzx Quux")
        self.assertIsNone(self.skill.active_person)

    def test_empty_popular_list_speaks_general_no_info(self):
        with patch.object(self.module, "Movie") as movie_cls:
            movie_cls.return_value.popular.return_value = []
            self.skill.handle_popular_movies(SimpleNamespace(data={}))
        self.assertEqual(self.spoken, [("no_info_general", None)])

    def test_popular_index_error_speaks_general_no_info(self):
        with patch.object(self.module, "Movie") as movie_cls:
            movie_cls.return_value.popular.side_effect = IndexError
            self.skill.handle_popular_movies(SimpleNamespace(data={}))
        self.assertEqual(self.spoken, [("no_info_general", None)])

    def test_top_index_error_speaks_general_no_info(self):
        with patch.object(self.module, "Movie") as movie_cls:
            movie_cls.return_value.top_rated.side_effect = IndexError
            self.skill.handle_top_movies(SimpleNamespace(data={}))
        self.assertEqual(self.spoken, [("no_info_general", None)])


if __name__ == "__main__":
    unittest.main()
