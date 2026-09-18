"""A bare genre goes to television; a genre with a movie noun does not.

`genre_tv_search.intent` gained two things: `series` as a television noun,
and a template for a genre with no noun at all ("i want to watch a
documentary"). The second one is a prefix of `movie_genre_search.intent`'s
"i want to watch [a|some] {genre} (movie|movies|film|films|flicks)", so the
two intents tie on the shared words and the longer literal match decides.

Today the movie intent wins its own phrasings. This module asserts both
directions, so a release that changes how a tie is broken fails here rather
than silently moving every movie request to television.
"""
from pathlib import Path

import pytest
from padacioso import IntentContainer

LOCALE = Path(__file__).resolve().parents[2] / "locale" / "en-US"


@pytest.fixture(scope="module")
def container():
    box = IntentContainer()
    for path in sorted(LOCALE.rglob("*.intent")):
        box.add_intent(path.stem, path.read_text(encoding="utf-8").splitlines())
    return box


@pytest.mark.parametrize("utterance", [
    "i want to watch a documentary",
    "show me some drama series",
    "list horror series",
    "list horror television shows",
])
def test_television_phrasings_go_to_the_television_intent(container, utterance):
    assert container.calc_intent(utterance).get("name") == "genre_tv_search"


@pytest.mark.parametrize("utterance", [
    "i want to watch a documentary film",
    "i want to watch a comedy movie",
    "find action movies",
    "show me some thriller films",
])
def test_movie_phrasings_still_go_to_a_movie_intent(container, utterance):
    """The control that matters: the bare-genre template steals nothing."""
    assert container.calc_intent(utterance).get("name") == "movie_genre_search"


def test_the_genre_slot_is_filled_not_just_matched(container):
    """A match that binds no slot would answer about no genre at all."""
    match = container.calc_intent("i want to watch a documentary")
    assert match.get("entities", {}).get("genre") == "documentary"


def test_an_unrelated_utterance_is_claimed_by_neither(container):
    """The control on the control: the container does not claim everything."""
    assert container.calc_intent("what is the weather tomorrow").get("name") is None
