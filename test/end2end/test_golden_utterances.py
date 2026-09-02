"""Golden-utterance end-to-end coverage for ovos-skill-moviemaster (en-US).

The golden corpus (``golden_utterances.jsonl``) is a vendored slice of the
shared ovoscope golden-utterance dataset, keyed by
``skill_id == "ovos-skill-moviemaster.openvoiceos"``. One shared
``MiniCroft`` (module-scoped fixture) is booted for the whole suite; every
row is its own parametrized test item so pytest gives each one a clean
setup/teardown boundary around bus listener registration (a single unittest
method looping 40 raw ``bus.on``/``bus.remove`` cycles was found to
degrade partway through on CI -- see PR discussion). The TMDB backend is
never reached: routing is asserted on the ``{skill_id}:{intent}`` bus
message, which fires before the handler runs (see
``test_intents_en_us.py``, whose pattern this suite follows), so the suite
stays deterministic and offline.

All 40 golden rows route correctly against the current en-US intent files;
no locale/vocab changes were needed.
"""
import json
import time
from pathlib import Path

import pytest
from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import get_minicroft

SKILL_ID = "ovos-skill-moviemaster.openvoiceos"
LANG = "en-US"

# The intent files are padatious samples. Exact expansions score in the -high
# band while the slotted variants land lower, so register all three bands
# (matches test_intents_en_us.py).
PIPELINE = [
    "ovos-padatious-pipeline-plugin-high",
    "ovos-padatious-pipeline-plugin-medium",
    "ovos-padatious-pipeline-plugin-low",
]

GOLDEN_PATH = Path(__file__).parent / "golden_utterances.jsonl"

# utterances lifted verbatim from OTHER skills' golden-utterance slices,
# picked for lexical overlap with this skill's "search"/"list"/"who"/"tell
# me about" vocabulary.
NEGATIVE_UTTERANCES = [
    ("tell me about happened this day", "ovos-skill-days-in-history.openvoiceos"),
    ("who is confucius", "ovos-skill-confucius-quotes.openvoiceos"),
    ("search wiki how for something", "ovos-skill-wikihow.openvoiceos"),
    ("search wolfram alpha for something", "ovos-skill-wolfie.openvoiceos"),
    ("search word net for word", "ovos-skill-wordnet.openvoiceos"),
    ("which lists are stored", "ovos-skill-alerts.openvoiceos"),
    ("create a shopping list", "ovos-skill-alerts.openvoiceos"),
]


def _load_golden_rows():
    rows = []
    with open(GOLDEN_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("needs_manual"):
                continue
            rows.append(row)
    return rows


def _normalize_intent_label(intent_label: str) -> str:
    """corpus "movie.description.intent" -> on-disk "movie_description"."""
    base = intent_label[:-len(".intent")] if intent_label.endswith(".intent") else intent_label
    return base.replace(".", "_")


GOLDEN_ROWS = _load_golden_rows()


@pytest.fixture(scope="module")
def minicroft():
    mc = get_minicroft([SKILL_ID])
    yield mc
    mc.stop()


def _fire(mc, text, session_id, listen_types, timeout=30):
    """Emit an utterance and collect any of ``listen_types`` fired in reply.

    Different padatious/padacioso plugin versions register the
    matched-intent bus event under different normalizations of the
    ``.intent`` filename basename -- observed variants include the bare
    basename with no extension and the basename with the extension kept
    (see ovos-skill-personal#113 for the same drift). Callers pass both
    wire forms as candidates instead of pinning one.
    """
    captured = []
    handler = lambda msg: captured.append(msg)
    for msg_type in listen_types:
        mc.bus.on(msg_type, handler)
    try:
        session = Session(session_id)
        session.lang = LANG
        session.pipeline = list(PIPELINE)
        mc.bus.emit(Message(
            "recognizer_loop:utterance",
            {"utterances": [text], "lang": LANG},
            {"session": session.serialize()},
        ))
        deadline = time.monotonic() + timeout
        while not captured and time.monotonic() < deadline:
            time.sleep(0.2)
    finally:
        for msg_type in listen_types:
            mc.bus.remove(msg_type, handler)
    return captured


def _golden_id(row):
    return row["utterance"]


@pytest.mark.parametrize("row", GOLDEN_ROWS, ids=_golden_id)
def test_golden_utterance(minicroft, row):
    base = _normalize_intent_label(row["intent_label"])
    candidates = {f"{SKILL_ID}:{base}", f"{SKILL_ID}:{base}.intent"}
    messages = _fire(minicroft, row["utterance"], f"golden-{_golden_id(row)}", candidates)
    got = [m.msg_type for m in messages]
    assert got and any(g in candidates for g in got), (
        f"{row['utterance']!r}: expected one of {sorted(candidates)!r}, got {got!r}"
    )


@pytest.mark.parametrize("negative", NEGATIVE_UTTERANCES, ids=lambda n: n[0])
def test_negative_confusable_not_claimed(minicroft, negative):
    """Utterances belonging to other skills must not be claimed by moviemaster.

    In a single-skill MiniCroft, an utterance nothing in the loaded skill
    set matches falls through padatious to ``complete_intent_failure`` (no
    ``ovos.intent.matched`` for this skill_id fires). Listening for both
    message types lets a genuine (buggy) match surface loudly instead of
    silently timing out.
    """
    text, source_skill = negative
    messages = _fire(
        minicroft, text, f"negative-{text}",
        ["ovos.intent.matched", "ovos.intent.unmatched", "complete_intent_failure"],
    )
    claimed = any(
        m.msg_type == "ovos.intent.matched"
        and str(m.data.get("intent_name", "")).startswith(f"{SKILL_ID}:")
        for m in messages
    )
    assert not claimed, f"{text!r} (from {source_skill}) was incorrectly claimed by {SKILL_ID}"
