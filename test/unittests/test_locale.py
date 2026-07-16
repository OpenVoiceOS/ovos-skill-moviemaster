"""Locale resource tests for ovos-skill-moviemaster.

Validates that the intent samples shipped for en-US expand cleanly and cover
every ``@intent_handler`` the skill registers, and that every locale directory
is a well-formed ``lang-REGION`` BCP-47 tag (OVOS-INTENT-2 §2).
"""
import os
import re
import unittest

from ovos_spec_tools import expand

REPO = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
LOCALE = os.path.join(REPO, "locale")
EN_US_VOCAB = os.path.join(LOCALE, "en-US", "vocab")

BCP47 = re.compile(r"^[a-z]{2,3}-[A-Z]{2}$")

# Intents referenced by an active @intent_handler in __init__.py.
HANDLER_INTENTS = {
    "movie_description.intent",
    "movie_year.intent",
    "movie_cast.intent",
    "movie_genres.intent",
    "movie_genre_search.intent",
    "genre_tv_search.intent",
    "movie_runtime.intent",
    "movie_recommendations.intent",
    "movie_popular.intent",
    "movie_top.intent",
}


def _lines(path):
    with open(path) as f:
        return [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]


class TestLocaleDirectories(unittest.TestCase):
    def test_every_locale_dir_is_valid_bcp47(self):
        for name in os.listdir(LOCALE):
            if not os.path.isdir(os.path.join(LOCALE, name)):
                continue
            self.assertRegex(
                name, BCP47,
                f"{name!r} is not a valid lang-REGION locale directory")


class TestEnUsIntents(unittest.TestCase):
    def test_handler_intents_have_locale_files(self):
        for intent in HANDLER_INTENTS:
            self.assertTrue(
                os.path.isfile(os.path.join(EN_US_VOCAB, intent)),
                f"missing en-US resource for {intent}")

    def test_intent_samples_expand(self):
        for intent in HANDLER_INTENTS:
            path = os.path.join(EN_US_VOCAB, intent)
            samples = []
            for line in _lines(path):
                samples.extend(expand(line))
            self.assertTrue(samples, f"{intent} produced no samples")


if __name__ == "__main__":
    unittest.main()
