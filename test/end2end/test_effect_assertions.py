"""Effect-assertion coverage for ovos-skill-moviemaster (en-US).

``test_intents_en_us.py`` and ``test_golden_utterances.py`` only assert that
an utterance reaches the expected ``{skill_id}:{intent}`` bus message -- the
message ovos-workshop fires *before* the ``@intent_handler`` runs. That is
satisfied by a handler which then raises, speaks nothing, or speaks the
wrong dialog: none of that is visible to a routing-only assertion.

This suite stubs the TMDB seam the skill actually calls (the ``Movie`` class
imported into ``ovos_skill_moviemaster``) with a fixed, synthetic payload
chosen independently of the code under test, then asserts the SPOKEN TEXT
carries that payload, rendered through the skill's own
``locale/en-US/dialog/movie_year.dialog`` template. No test in this module
makes a real network call: ``Movie`` and ``TMDb`` are replaced with mocks
before the skill is even loaded, so neither the skill's own TMDB lookup nor
its startup ``verify_api`` probe (``Movie().popular()``) ever reaches
themoviedb.org, regardless of whatever ``apiv3`` value a local
``settings.json`` may already carry on the host running the test.
"""
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovos_date_parser import nice_date
from ovoscope import get_minicroft

import ovos_skill_moviemaster as skill_module

SKILL_ID = "ovos-skill-moviemaster.openvoiceos"
LANG = "en-US"
PIPELINE = [
    "ovos-padatious-pipeline-plugin-high",
    "ovos-padatious-pipeline-plugin-medium",
    "ovos-padatious-pipeline-plugin-low",
]

DIALOG_DIR = Path(__file__).resolve().parents[2] / "locale" / "en-US" / "dialog"

# A fixed, obviously-synthetic TMDB payload. The values are chosen here, by
# the test, independently of the skill: a handler that ignores this movie,
# reads the wrong field, or speaks a hardcoded string fails the assertion
# below.
_FAKE_MOVIE = SimpleNamespace(
    title="The Matrix",
    release_date="2001-02-03",
    id=999999,
    overview="",
)


def _fake_movie_class():
    mock_cls = MagicMock()
    mock_cls.return_value.search.return_value = [_FAKE_MOVIE]
    mock_cls.return_value.popular.return_value = [_FAKE_MOVIE]
    return mock_cls


@pytest.fixture(scope="module")
def minicroft():
    movie_patcher = patch.object(skill_module, "Movie", _fake_movie_class())
    tmdb_patcher = patch.object(skill_module, "TMDb")
    movie_patcher.start()
    tmdb_patcher.start()
    try:
        mc = get_minicroft([SKILL_ID], lang=LANG)
        loader = mc.plugin_skills[SKILL_ID]
        # Guarantee a truthy api_key regardless of whatever real value a
        # host settings.json for this skill id might otherwise supply --
        # Movie/TMDb are mocks either way, so this never triggers a real
        # lookup, it only satisfies the skill's own `if not self.api_key`
        # guards.
        loader.instance._api_key = "test-key-not-a-real-tmdb-key"
        yield mc
        mc.stop()
    finally:
        movie_patcher.stop()
        tmdb_patcher.stop()


def _spoken(mc, utterance, session_id, timeout=30):
    spoken = []
    handler = lambda m: spoken.append(m.data.get("utterance", ""))
    mc.bus.on("speak", handler)
    try:
        session = Session(session_id)
        session.lang = LANG
        session.pipeline = list(PIPELINE)
        mc.bus.emit(Message(
            "recognizer_loop:utterance",
            {"utterances": [utterance], "lang": LANG},
            {"session": session.serialize()},
        ))
        deadline = time.monotonic() + timeout
        while not spoken and time.monotonic() < deadline:
            time.sleep(0.2)
        # give a slow handler a little more room after the first utterance
        time.sleep(1.0)
    finally:
        mc.bus.remove("speak", handler)
    return spoken


@pytest.mark.timeout(60)
def test_movie_year_speaks_the_fetched_year_and_title(minicroft):
    """FAILS if the handler never speaks, speaks the wrong dialog, or
    reports a year/title other than the one the (mocked) TMDB response
    carries -- none of which a routing-only assertion can catch.
    """
    dialog_template = (DIALOG_DIR / "movie_year.dialog").read_text(encoding="utf-8")
    assert "{movie}" in dialog_template and "{year}" in dialog_template

    spoken = _spoken(
        minicroft, "what year was the movie the matrix released", "effect-movie-year")
    joined = " ".join(spoken)

    # Computed independently of the skill: same rendering call it uses for
    # the {year} placeholder, applied here to the fixed payload's own
    # release_date -- the assertion below fails if the handler renders a
    # different date (wrong field, unrelated movie, stale cache, ...).
    expected_year_phrase = nice_date(datetime(2001, 2, 3), lang=LANG)

    assert spoken, "movie_year handler never spoke anything"
    assert "matrix" in joined.lower(), (
        f"expected the fetched movie title 'The Matrix' in spoken text, got {spoken!r}")
    assert expected_year_phrase.lower() in joined.lower(), (
        f"expected the fetched release date {expected_year_phrase!r} in spoken text, got {spoken!r}")
