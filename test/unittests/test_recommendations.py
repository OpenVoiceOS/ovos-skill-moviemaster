"""``handle_movie_recommendations`` when it has no movie to recommend from.

The handler gets no ``movie`` slot when the intent matcher binds none, and
it finds no movie when the API key is missing or TMDb returns no title that
matches. In each case it must speak a dialog and return, and it must not
reach TMDb with an empty title.
"""
import importlib.util
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

REPO = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
INIT_PY = os.path.join(REPO, "__init__.py")


def _load_skill_module():
    spec = importlib.util.spec_from_file_location("moviemaster_init", INIT_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestRecommendationsWithoutMovie(unittest.TestCase):

    def setUp(self):
        self.module = _load_skill_module()
        self.skill = self.module.MovieMaster.__new__(self.module.MovieMaster)
        self.skill._api_key = "test-key-not-a-real-tmdb-key"
        self.skill._search_depth = 5
        self.skill._match_confidence = 0.8
        self.skill._active_movie = None
        self.skill._active_person = None
        self.skill._settings = {"match_confidence": 0.8}
        # TMDb is mocked below; the language lookup needs a booted skill.
        self.skill._configure_tmdb = lambda: None
        self.spoken = []
        self.skill.speak_dialog = \
            lambda dialog, data=None: self.spoken.append((dialog, data))

    def _handle(self, data):
        message = SimpleNamespace(data=data)
        with patch.object(self.module, "Movie") as movie_cls, \
                patch.object(self.module, "TMDb"):
            movie_cls.return_value.search.return_value = []
            self.skill.handle_movie_recommendations(message)
        return movie_cls

    def test_no_movie_slot_speaks_general_no_info(self):
        movie_cls = self._handle({})
        self.assertEqual(self.spoken, [("no_info_general", None)])
        movie_cls.assert_not_called()

    def test_empty_movie_slot_speaks_general_no_info(self):
        movie_cls = self._handle({"movie": ""})
        self.assertEqual(self.spoken, [("no_info_general", None)])
        movie_cls.assert_not_called()

    def test_unknown_movie_speaks_no_info_for_that_movie(self):
        movie_cls = self._handle({"movie": "Zyxwv Unknown"})
        self.assertEqual(self.spoken,
                         [("no_info", {"movie": "Zyxwv Unknown"})])
        movie_cls.return_value.search.assert_called_once_with("Zyxwv Unknown")
        movie_cls.return_value.recommendations.assert_not_called()

    def test_missing_api_key_speaks_only_the_api_dialog(self):
        self.skill._api_key = None
        movie_cls = self._handle({"movie": "Titanic"})
        self.assertEqual(self.spoken, [("no_valid_api", {})])
        movie_cls.assert_not_called()

    def test_found_movie_still_speaks_recommendations(self):
        titanic = SimpleNamespace(id=597, title="Titanic")
        message = SimpleNamespace(data={"movie": "Titanic"})
        with patch.object(self.module, "Movie") as movie_cls, \
                patch.object(self.module, "TMDb"):
            movie_cls.return_value.search.return_value = [titanic]
            movie_cls.return_value.recommendations.return_value = [
                {"title": "Synthetic One"}, {"title": "Synthetic Two"}]
            self.skill.handle_movie_recommendations(message)
        self.assertEqual(self.spoken, [("movie_recommendations", {
            "movielist": "Synthetic One, ", "lastmovie": "Synthetic Two",
            "movie": "Titanic"})])


if __name__ == "__main__":
    unittest.main()
