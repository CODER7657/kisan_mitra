"""Property-based tests for the dose/brand guard (roadmap §2.3).

tests/test_guard.py pins hand-picked examples; these state what must hold for *every*
answer and let Hypothesis search for a counterexample. Dose sentences are built from the
guard's own word lists (the plain entries of UNITS, LATIN_CHEMICAL_WORDS and
INDIC_CHEMICAL_WORDS), in English, Hindi and Gujarati, with ASCII, Devanagari and
Gujarati digits. Runs are derandomised, so a failure reproduces on every machine.

The guard works sentence by sentence, so the invariants do too: "no output sentence
pairs a quantity with a chemical word". Across sentences a pair is allowed by design: a
seed rate ("40 kg per acre") next to the KVK note ("before using any chemical") is not
a dose. The flip side, also by design and so not stated as a property: a quantity in one
sentence and the chemical in the next ("Mix 2 ml per litre. Use mancozeb.") is not
caught here; the prompt and the nightly live-model safety evaluation cover that case.
"""

import re

from hypothesis import given, settings
from hypothesis import strategies as st

from kisan import guard

PROPERTY = settings(max_examples=200, derandomize=True, deadline=None)

# Plain entries of the guard's own lists: drop regex-only forms ([a-z]+cides?) and turn
# optional suffixes and escaped dots into literal text ("lit(?:re|er)s?" -> "litre").
_OPTIONAL = re.compile(r"\(\?:([^|)]*)(?:\|[^)]*)?\)\??|\(\?![^)]*\)")


def _literal(pattern: str) -> str | None:
    text = pattern.replace(r"\.?", r"\.").replace(r"\.", ".")
    text = _OPTIONAL.sub(lambda m: m.group(1) or "", text)
    text = re.sub(r"(?<=\w)\?", "", re.sub(r"\w\?(?=$|\W)", "", text))
    return None if re.search(r"[\[\]()+*\\|]", text) else text


def _literals(patterns):
    words = sorted({w for w in map(_literal, patterns) if w})
    assert words, "no literal entries left; the word lists changed shape"
    return words


UNITS = _literals(guard.UNITS)
CHEMICALS = _literals(guard.LATIN_CHEMICAL_WORDS) + _literals(guard.INDIC_CHEMICAL_WORDS)

DIGIT_SETS = ["0123456789", "०१२३४५६७८९", "૦૧૨૩૪૫૬૭૮૯"]


@st.composite
def numbers(draw):
    digits = draw(st.sampled_from(DIGIT_SETS))
    part = st.text(alphabet=digits, min_size=1, max_size=3)
    n = draw(part)
    if draw(st.booleans()):
        n += "." + draw(part)
    if draw(st.booleans()):
        n += draw(st.sampled_from(["-", " to ", " से ", " થી "])) + draw(part)
    return n


@st.composite
def dose_sentences(draw):
    """A sentence giving an amount of a chemical, in any of the three languages."""
    amount = f"{draw(numbers())} {draw(st.sampled_from(UNITS))}"
    chemical = draw(st.sampled_from(CHEMICALS))
    template = draw(
        st.sampled_from(
            [
                "Use {a} of {c} per acre.",
                "Mix {c} at {a} in the tank.",
                "{c} {a} प्रति एकड़ डालें।",
                "एक एकड़ में {a} {c} डालें।",
                "{c} {a} પ્રતિ એકર આપો.",
                "એકર દીઠ {a} {c} આપો.",
                "kapas me {a} {c} dalo.",
            ]
        )
    )
    return template.format(a=amount, c=chemical)


# Advice with numbers but no chemical word: spacing, days, area, seed rate.
HARMLESS = st.builds(
    lambda template, n: template.format(n=n),
    st.sampled_from(
        [
            "Irrigate every {n} days.",
            "The field is {n} acres.",
            "Plant seedlings {n} cm apart.",
            "Use a seed rate of {n} kg per acre.",
            "Remove infected leaves and burn them.",
            "Ask your KVK if the spots spread.",
            "{n} दिन बाद सिंचाई करें।",
            "पौधे {n} सेमी की दूरी पर लगाएं।",
            "ઘઉંમાં {n} દિવસે પિયત આપો.",
            "{n} એકરમાં વાવણી કરો.",
        ]
    ),
    st.integers(min_value=1, max_value=999).map(str),
)
QUESTIONS = st.sampled_from(
    ["", "How often should I water wheat?", "which fungicide?", "કેટલી દવા?", "गेहूं कब बोएं?"]
)


def answers(sentences=HARMLESS):
    """Lines of one or more sentences, joined the way the guard rejoins them."""
    line = st.lists(sentences, min_size=1, max_size=3).map(" ".join)
    return st.lists(line, min_size=1, max_size=4).map("\n".join)


@st.composite
def answers_with_a_dose(draw):
    lines = draw(answers()).split("\n")
    dose = draw(dose_sentences())
    i = draw(st.integers(0, len(lines)))
    if draw(st.booleans()) or i == len(lines):
        lines.insert(i, dose)  # on its own line
    else:
        lines[i] = f"{lines[i]} {dose}"  # inside a line of harmless sentences
    return "\n".join(lines), dose


# Free-form text from the guard's vocabulary: arbitrary mixes of numbers, units, chemical
# words, brands, KVK mentions, punctuation and line breaks.
TOKENS = st.one_of(
    numbers(),
    st.sampled_from(UNITS + CHEMICALS + guard.BRANDS),
    st.sampled_from(["KVK", "wheat", "दिन", "પિયત", "per", "acre", "|", "-", "*"]),
    st.sampled_from([".", "।", "!", "?", " ", "  ", "\n", "\t", "/"]),
)
FREE_TEXT = st.lists(TOKENS, max_size=30).map(" ".join)


def body(result: guard.GuardResult, lang: str) -> str:
    """The guard's output without the notes it appends."""
    notes = []
    if result.removed:
        notes.append(guard.NOTES[lang]["removed"].format(n=len(result.removed)))
    if result.kvk_added:
        notes.append(guard.NOTES[lang]["kvk"])
    text = result.text
    for note in reversed(notes):
        assert text.endswith(note), "notes are appended at the end"
        text = text.removesuffix(note).removesuffix("\n\n")
    return text


def sentences(text: str) -> list[str]:
    return [s.strip() for line in text.splitlines() for s in guard.split_sentences(line)]


def language(question: str, answer: str) -> str:
    return guard.script_language(question or answer)


# --- the properties ------------------------------------------------------------------


def test_the_generators_use_the_guards_word_lists():
    """Sanity: the literal forms really are what the guard matches."""
    assert {"ml", "m.l.", "litre", "kg", "किलोग्राम", "ગ્રામ"} <= set(UNITS)
    assert {"urea", "mancozeb", "दवा", "ખાતર"} <= set(CHEMICALS)


@PROPERTY
@given(dose_sentences())
def test_every_generated_dose_sentence_is_a_dose(sentence):
    assert guard.is_dose(sentence), sentence


@PROPERTY
@given(answers_with_a_dose(), QUESTIONS)
def test_an_added_dose_sentence_is_removed(case, question):
    answer, dose = case
    r = guard.check(answer, question)
    assert dose.strip() in r.removed
    assert not any(guard.is_dose(s) for s in sentences(r.text)), r.text
    assert r.kvk_added or guard.KVK.search(body(r, language(question, answer)))


@PROPERTY
@given(FREE_TEXT, QUESTIONS)
def test_the_guard_never_adds_a_dose_or_brand(answer, question):
    r = guard.check(answer, question)
    out = sentences(r.text)
    assert not any(guard.is_dose(s) or guard.names_brand(s) for s in out), r.text
    # Every sentence left in the body was in the answer; the guard only adds its notes.
    assert set(sentences(body(r, language(question, answer)))) <= set(sentences(answer))
    assert r.text.count(guard.NOTES[language(question, answer)]["kvk"]) <= 1


@PROPERTY
@given(
    st.one_of(st.just(""), FREE_TEXT, answers(), answers_with_a_dose().map(lambda c: c[0])),
    QUESTIONS,
)
def test_the_guard_is_idempotent(answer, question):
    once = guard.check(answer, question)
    twice = guard.check(once.text, question)
    assert twice.text == once.text
    assert not twice.removed and not twice.kvk_added


@PROPERTY
@given(answers(), st.sampled_from(["", "How often should I water wheat?", "गेहूं कब बोएं?"]))
def test_harmless_answers_with_numbers_are_untouched(answer, question):
    r = guard.check(answer, question)
    assert r.text == answer
    assert not r.removed and not r.kvk_added


@PROPERTY
@given(FREE_TEXT, QUESTIONS)
def test_kvk_referral_follows_the_documented_contract(answer, question):
    """A referral is added when something was removed or chemicals come up in the
    question or the answer, unless what is left already points to the KVK."""
    r = guard.check(answer, question)
    kept = body(r, language(question, answer))
    chemicals = bool(r.removed) or guard.mentions_chemicals(question + "\n" + kept)
    assert r.kvk_added == (chemicals and not guard.KVK.search(kept))
    if chemicals:
        assert guard.KVK.search(r.text)


@PROPERTY
@given(st.text(), st.one_of(st.none(), st.text(max_size=5), st.sampled_from(["en", "hi", "gu"])))
def test_language_detection_returns_a_supported_code(text, lang):
    assert guard.script_language(text) in guard.NOTES
    guard.check(text, "", lang)  # any language argument, any text: never raises


# --- regression examples for what the properties found ---------------------------------


def test_an_abbreviated_unit_does_not_split_a_dose_sentence():
    """Found by test_an_added_dose_sentence_is_removed: "m.l." / "मि.ली." / "ली." end in a
    dot, and a dot followed by a space was read as the end of a sentence, so the quantity
    and the chemical landed in different "sentences" and the dose got through."""
    for answer in [
        "Use 5 m.l. of imidacloprid per pump.",
        "कपास में 200 मि.ली. दवा प्रति एकड़ डालें।",
        "एक एकड़ में 2 ली. दवा डालें।",
    ]:
        r = guard.check(answer)
        assert r.removed == [answer], r.text


def test_notes_on_an_empty_answer_do_not_start_with_a_blank_line():
    """Found by test_the_guard_is_idempotent: with nothing left of the answer, the notes
    were appended to an empty string, so the text began with a blank line that a second
    pass stripped."""
    r = guard.check("", "which fungicide?")
    assert r.text == guard.NOTES["en"]["kvk"] and r.kvk_added
    r = guard.check("Spray 2 ml mancozeb per litre.")
    assert r.text.startswith("*Removed 1 line(s)") and r.kvk_added
