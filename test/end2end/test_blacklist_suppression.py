"""The sibling-word blacklists suppress the intent that must not answer.

Every ``locale/<lang>/vocab/<intent>.blacklist`` file lists the content
words that mark a SIBLING question in that locale. OVOS-INTENT-2 §4.3:
the words suppress the intent the file sits beside. A match is at word
boundaries, so each entry is a whole word or phrase as that locale
writes it.

Each case below is a pair, not one utterance:

* the control is a literal resolution of the locale's own
  ``movie_runtime.intent`` template line, the same way every row in
  ``golden_utterances_<lang>.jsonl`` is built, with ``{movie}`` filled
  with ``Stripes``. It must route to ``movie_runtime``.
* the probe is that control with one word from
  ``movie_runtime.blacklist`` added. It must NOT route to
  ``movie_runtime``.

The probe is a suppression probe and not a phrasing a person would say,
so it is not added to the golden corpus. The pair is what gives it
meaning: without the blacklist file both halves route to
``movie_runtime``, which is the defect these files close.

Other intents may legitimately answer the probe, because it carries
another question's word. Only ``movie_runtime`` is asserted against.

Two limits, measured and named rather than hidden:

* eu-ES does not discriminate. Appending ANY word to the Basque control
  stops the template matching on its own, so the eu-ES probe passes
  with the blacklist file removed as well. The row still asserts real
  behaviour, but it is not evidence that the eu-ES file works. Every
  other locale fails with its file removed.
* fr-FR uses ``synopsis`` and not a hyphenated entry. padacioso matches
  a space-free keyword by token equality, and an intent excluded that
  way can still be returned: ``recommande-moi`` puts ``movie_runtime``
  in ``_filter`` and ``calc_intent`` returns it anyway with conf 0.96.
  The hyphenated entries stay in the locale file, because they are how
  French writes the word; they do not bite until that is fixed.
"""
import pytest
from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import CaptureSession, get_minicroft

SKILL_ID = "ovos-skill-moviemaster.openvoiceos"

PIPELINE = [
    "ovos-padacioso-pipeline-plugin-high",
    "ovos-padacioso-pipeline-plugin-medium",
    "ovos-padacioso-pipeline-plugin-low",
]

FORBIDDEN = "movie_runtime"

# (lang, control utterance, the blacklist word added to make the probe)
CASES = [
    ('ca-ES', 'Digues la duració de el film Stripes', 'recomana'),
    ('da-DK', 'Få længden af film Stripes', 'anbefal'),
    ('de-DE', 'Was ist die laufzeit vom Film Stripes', 'empfehle'),
    ('es-ES', 'Cuánto dura el filme Stripes', 'recomienda'),
    ('eu-ES', 'Lortu Stripes filmaren iraupena', 'gomendatu'),
    ('fr-FR', 'combien de temps dure le film Stripes', 'synopsis'),
    ('gl-ES', 'Busca canto dura a peli Stripes', 'recomenda'),
    ('it-IT', 'Qual è la durata de Stripes', 'raccomanda'),
    ('pt-BR', 'Diga a duração da filme Stripes', 'recomende'),
    ('sv-SE', 'Hur lång är film Stripes', 'rekommendera'),
    ('en-US', 'Get the length of the film Stripes', 'recommend'),
]

# One MiniCroft alive at a time, stopped when the locale changes: two alive
# together each hold the other's lang as "original" and the restore chain
# leaves the process on a foreign locale (see
# test_golden_utterances_multilang.py, same pattern).
_CURRENT = {"lang": None, "mc": None}


def _get_minicroft(lang):
    if _CURRENT["lang"] != lang:
        _stop_current()
        _CURRENT["mc"] = get_minicroft([SKILL_ID], max_wait=150, lang=lang,
                                       default_pipeline=PIPELINE)
        _CURRENT["lang"] = lang
    return _CURRENT["mc"]


def _stop_current():
    if _CURRENT["mc"] is not None:
        _CURRENT["mc"].stop()
    _CURRENT["mc"] = None
    _CURRENT["lang"] = None


@pytest.fixture(scope="module", autouse=True)
def _stop_last_minicroft():
    yield
    _stop_current()


def _types(mc, text, lang, session_id):
    session = Session(session_id)
    session.lang = lang
    session.pipeline = list(PIPELINE)
    session.blacklisted_intents = []
    utterance = Message(
        "recognizer_loop:utterance",
        {"utterances": [text], "lang": lang},
        {"session": session.serialize(), "source": "A", "destination": "B"},
    )
    capture = CaptureSession(mc, eof_msgs=["mycroft.skill.handler.start"])
    capture.capture(utterance, timeout=30)
    return [m.msg_type for m in capture.finish()]


@pytest.mark.timeout(300)
@pytest.mark.parametrize("lang,control,word", CASES, ids=lambda v: str(v))
def test_blacklist_word_suppresses_the_intent(lang, control, word):
    mc = _get_minicroft(lang)
    forbidden = {f"{SKILL_ID}:{FORBIDDEN}", f"{SKILL_ID}:{FORBIDDEN}.intent"}

    types = _types(mc, control, lang, f"control-{lang}")
    assert any(t in forbidden for t in types), (
        f"[{lang}] control {control!r} did not route to {FORBIDDEN}: {types!r}")

    probe = f"{control} {word}"
    types = _types(mc, probe, lang, f"probe-{lang}")
    assert not any(t in forbidden for t in types), (
        f"[{lang}] {probe!r} still routed to {FORBIDDEN}; "
        f"{lang}/vocab/{FORBIDDEN}.blacklist lists {word!r}: {types!r}")
