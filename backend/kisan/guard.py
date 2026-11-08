"""Deterministic checks on the model's answer before a farmer sees it.

The model is told not to give chemical doses or brands. This guard makes sure of it:
a sentence that pairs a quantity with a chemical word (or names a known brand) is
removed, and a KVK referral is added wherever chemicals come up. Quantities that are
not chemical doses (plant spacing, irrigation days, seed rate) are left alone.
"""

import re
from dataclasses import dataclass, field

DIGITS = r"[0-9०-९૦-૯]"  # ASCII, Devanagari and Gujarati digits
NUMBER = rf"{DIGITS}+(?:[.,]{DIGITS}+)?(?:\s*(?:-|to|से|થી)\s*{DIGITS}+(?:[.,]{DIGITS}+)?)?"
UNITS = [
    r"ml",
    r"m\.l\.?",
    r"millilit(?:re|er)s?",
    r"l",
    r"lit(?:re|er)s?",
    r"lit",
    r"lt",
    r"ltr",
    r"g",
    r"gm",
    r"gms",
    r"grams?",
    r"kg",
    r"kgs",
    r"kilo(?:gram)?s?",
    r"quintals?",
    r"ppm",
    r"%",
    r"cc",
    r"tablespoons?",
    r"spoons?",
    r"bags?",
    r"packets?",
    r"bottles?",
    r"मिली",
    r"मि\.ली\.?",
    # Short Hindi/Gujarati abbreviations only with their dot, so "5 લીલા પાન" (5 green
    # leaves) is not read as 5 litres.
    r"लि\.",
    r"ग्रा\.",
    r"कि\.?ग्रा\.",
    r"एमएल",
    r"लीटर",
    r"ली\.?",
    r"ग्राम",
    r"किलो(?:ग्राम)?",
    r"किग्रा",
    r"मिलीलीटर",
    r"चम्मच",
    r"बोरी",
    r"थैली",
    r"મિલી",
    r"મિ\.લી\.?",
    r"લિ\.",
    r"લી\.",
    r"ગ્રા\.",
    r"કિ\.?ગ્રા\.",
    r"એમએલ",
    r"લિટર",
    r"લીટર",
    r"ગ્રામ",
    r"કિલો(?:ગ્રામ)?",
    r"ચમચી",
    r"થેલી",
    r"બોરી",
]
# Any unit may be written with a trailing dot ("5 kg.", "10 gm.", "2 ली.", "5 મિ.લી."): the dot
# is part of the quantity, not the end of a sentence (see split_sentences).
QUANTITY = re.compile(rf"{NUMBER}\s*(?:{'|'.join(UNITS)})\.?(?![a-z])", re.IGNORECASE)

LATIN_CHEMICAL_WORDS = [
    r"pesticides?",
    r"insecticides?",
    r"fungicides?",
    r"herbicides?",
    r"weedicides?",
    r"bactericides?",
    r"fertili[sz]ers?",
    r"urea",
    r"dap",
    r"mop",
    r"npk",
    r"ssp",
    r"potash",
    r"sulph?ate",
    r"chemicals?",
    r"sprays?",
    r"spraying",
    r"dose",
    r"dosage",
    r"[a-z]+cides?",
    r"[a-z]+phos",
    r"[a-z]+azole",
    r"[a-z]+thrin",
    r"imidacloprid",
    r"mancozeb",
    r"carbendazim",
    r"thiamethoxam",
    r"acephate",
    r"emamectin",
    r"metalaxyl",
    r"copper oxychloride",
    r"glyphosate",
    r"chlorantraniliprole",
    r"spinosad",
    r"fipronil",
    r"sulphur",
    r"sulfur",
    r"neem oil",
    r"zineb",
    r"thiram",
    r"captan",
    r"streptocycline",
    r"dawai",
    r"dawa",
    r"khad",  # romanised Hindi
]
# Hindi and Gujarati words take suffixes (દવાનો, दवाओं), so they match as prefixes, except where a
# longer word means something else: ખાતરી is "certainty", not ખાતર "fertiliser"; खादी is cloth.
INDIC_CHEMICAL_WORDS = [
    r"दवा",
    r"कीटनाशक",
    r"फफूंदनाशक",
    r"खरपतवारनाशक",
    r"खाद(?!ी)",
    r"उर्वरक",
    r"यूरिया",
    r"डीएपी",
    r"पोटाश",
    r"छिड़काव",
    r"छिडकाव",
    r"स्प्रे",
    r"रसायन",
    r"मैनकोजेब",
    r"इमिडाक्लोप्रिड",
    r"દવા",
    r"જંતુનાશક",
    r"ફૂગનાશક",
    r"નીંદણનાશક",
    r"ખાતર(?!ી)",
    r"યુરિયા",
    r"ડીએપી",
    r"પોટાશ",
    r"છંટકાવ",
    r"સ્પ્રે",
    r"રસાયણ",
    r"મેન્કોઝેબ",
]
CHEMICAL = re.compile(
    r"(?<![a-z])(?:"
    + "|".join(LATIN_CHEMICAL_WORDS)
    + r")(?![a-z])|"
    + "|".join(INDIC_CHEMICAL_WORDS),
    re.IGNORECASE,
)

# Well-known Indian crop-protection brand names. Not complete; the prompt asks for none.
BRANDS = [
    "confidor",
    "admire",
    "actara",
    "coragen",
    "tracer",
    "ridomil",
    "dithane",
    "indofil",
    "saaf",
    "bavistin",
    "roundup",
    "glycel",
    "regent",
    "nuvan",
    "rogor",
    "monocil",
    "hamla",
    "ulala",
    "pegasus",
    "contaf",
    "blitox",
    "kavach",
    "amistar",
    "nativo",
    "antracol",
    "curzate",
    "proclaim",
]
BRAND = re.compile(r"\b(?:" + "|".join(BRANDS) + r")\b", re.IGNORECASE)

KVK = re.compile(
    r"kvk|krishi vigyan kendra|कृषि विज्ञान केंद्र|कृषि विज्ञान केन्द्र|કૃષિ વિજ્ઞાન કેન્દ્ર", re.IGNORECASE
)

SENTENCE_END = re.compile(r"(?<=[.!?।])\s+")
# A part that ends in a quantity whose unit is followed by a dot ("5 kg.", "2 ली.") is not a
# finished sentence: splitting there would put the amount and the chemical in different
# sentences and let the dose through. Built from QUANTITY, so every unit (and any unit added
# later) is covered without a second list. Erring this way can merge a real sentence ending
# in a quantity with the next one; the cost is an over-cautious removal, never a leaked dose.
QUANTITY_DOT_END = re.compile(rf"(?:{QUANTITY.pattern})(?<=\.)$", re.IGNORECASE)

NOTES = {
    "en": {
        "removed": "*Removed {n} line(s) that gave a chemical dose or brand. Kisan Mitra does not give doses.*",
        "kvk": "Before using any chemical, confirm the product and the dose with your local Krishi Vigyan "
        "Kendra (KVK) or agriculture officer, and read the label.",
    },
    "hi": {
        "removed": "*{n} पंक्ति(याँ) हटाई गईं जिनमें दवा की मात्रा या ब्रांड था। किसान मित्र दवा की मात्रा नहीं बताता।*",
        "kvk": "किसी भी दवा का इस्तेमाल करने से पहले उत्पाद और मात्रा अपने नज़दीकी कृषि विज्ञान केंद्र (KVK) "
        "या कृषि अधिकारी से पक्का करें, और लेबल पढ़ें।",
    },
    "gu": {
        "removed": "*{n} લીટી દૂર કરી, જેમાં દવાની માત્રા અથવા બ્રાન્ડ હતી. કિસાન મિત્ર દવાની માત્રા આપતું નથી.*",
        "kvk": "કોઈપણ દવા વાપરતા પહેલાં તેનું નામ અને માત્રા તમારા નજીકના કૃષિ વિજ્ઞાન કેન્દ્ર (KVK) અથવા "
        "ખેતીવાડી અધિકારી પાસેથી નક્કી કરો, અને લેબલ વાંચો.",
    },
}


def script_language(text: str) -> str:
    """Language by script: Gujarati, Devanagari (Hindi) or anything else (English)."""
    gu = sum("઀" <= c <= "૿" for c in text)
    hi = sum("ऀ" <= c <= "ॿ" for c in text)
    if gu == 0 and hi == 0:
        return "en"
    return "gu" if gu >= hi else "hi"


def split_sentences(line: str) -> list[str]:
    """Sentences of one line. A merged sentence keeps the original text between its parts,
    so a removed sentence is always an exact substring of the answer."""
    sentences: list[str] = []
    start = sentence_start = 0
    for match in [*SENTENCE_END.finditer(line), None]:
        end = match.start() if match else len(line)
        if sentences and QUANTITY_DOT_END.search(sentences[-1]):
            sentences[-1] = line[sentence_start:end]
        else:
            sentences.append(line[start:end])
            sentence_start = start
        if match:
            start = match.end()
    return sentences


def is_dose(sentence: str) -> bool:
    return bool(QUANTITY.search(sentence)) and bool(CHEMICAL.search(sentence))


def names_brand(sentence: str) -> bool:
    return bool(BRAND.search(sentence))


def mentions_chemicals(text: str) -> bool:
    return bool(CHEMICAL.search(text))


@dataclass
class GuardResult:
    text: str
    removed: list[str] = field(default_factory=list)
    kvk_added: bool = False


def check(answer: str, question: str = "", language: str | None = None) -> GuardResult:
    lang = language if language in NOTES else script_language(question or answer)
    notes = NOTES[lang]
    removed: list[str] = []
    out_lines = []
    for line in answer.splitlines():
        sentences = split_sentences(line)
        kept = [s for s in sentences if not (is_dose(s) or names_brand(s))]
        removed += [s.strip() for s in sentences if s not in kept]
        new = " ".join(kept).rstrip()
        # A line left with only list markers or table pipes after removal is dropped.
        if len(kept) < len(sentences) and not re.search(r"\w", new):
            continue
        out_lines.append(new)
    kept_text = "\n".join(out_lines).strip()
    parts = [kept_text]
    if removed:
        parts.append(notes["removed"].format(n=len(removed)))
    # The notes never name the KVK, so what is left of the answer decides the referral.
    kvk_added = bool(
        removed or mentions_chemicals(question) or mentions_chemicals(kept_text)
    ) and not KVK.search(kept_text)
    if kvk_added:
        parts.append(notes["kvk"])
    # Notes follow the answer after a blank line; with nothing left of the answer, the text
    # starts with the first note rather than a blank line.
    text = "\n\n".join(p for p in parts if p)
    return GuardResult(text=text, removed=removed, kvk_added=kvk_added)
