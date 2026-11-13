"""Deterministic checks on the model's answer before a farmer sees it.

The model is told not to give chemical doses or brands. This guard makes sure of it:
a sentence that pairs a quantity with a chemical word (or names a known brand) is
removed, and a KVK referral is added wherever chemicals come up. Quantities that are
not chemical doses (plant spacing, irrigation days, seed rate) are left alone.
"""

import re
import unicodedata
from dataclasses import dataclass, field

DIGITS = r"[0-9०-९૦-૯]"  # ASCII, Devanagari and Gujarati digits
# An amount can be spelled out ("ten ml", "दस मिली", "બે મિલી"). A number word counts only
# when a unit follows it (see QUANTITY), so "one of the leaves" is not a quantity.
NUMBER_WORDS = (
    r"(?<![a-z])(?:half|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen"
    r"|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|few|couple of)(?![a-z])"
    r"|(?<![ऀ-ॿ])(?:आधा|आधी|एक|डेढ़|दो|ढाई|तीन|चार|पांच|पाँच|छह|छः|सात|आठ|नौ|दस|बीस|तीस|चालीस|पचास|सौ|हजार|हज़ार)(?![ऀ-ॿ])"
    r"|(?<![઀-૿])(?:અડધો|અડધી|અડધું|એક|દોઢ|બે|અઢી|ત્રણ|ચાર|પાંચ|છ|સાત|આઠ|નવ|દસ|વીસ|ત્રીસ|ચાલીસ|પચાસ|સો|હજાર)(?![઀-૿])"
)
NUMBER = (
    rf"(?:{DIGITS}+(?:[.,/]{DIGITS}+)?(?:\s*(?:-|to|से|થી)\s*{DIGITS}+(?:[.,/]{DIGITS}+)?)?"
    rf"|(?:{NUMBER_WORDS}))"
)
UNITS = [
    r"ml",
    r"mls",
    r"m\.l\.?",
    r"mg",
    r"mgs",
    r"milligrams?",
    r"oz",
    r"ounces?",
    r"tsp",
    r"tbsp",
    r"teaspoons?",
    r"drops?",
    r"caps?",
    r"capfuls?",
    r"lids?",
    r"percent",
    r"per\s?cent",
    r"बूंद",
    r"बूँद",
    r"ढक्कन",
    r"प्रतिशत",
    r"ટીપાં",
    r"ટીપા",
    r"ઢાંકણ",
    r"ટકા",
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
# A dilution ratio ("1:500") is a dose as well; three digits on the right keep clock times out.
QUANTITY = re.compile(
    rf"{NUMBER}\s*(?:{'|'.join(UNITS)})\.?(?![a-z])|{DIGITS}+\s*:\s*{DIGITS}{{3,}}", re.IGNORECASE
)


def fold(text: str) -> str:
    """The text as the patterns should see it; used for matching only, never shown.

    Invisible format characters (zero-width space or joiner, soft hyphen, BOM) are dropped,
    full-width letters and digits become ASCII, digits of any other script become ASCII
    digits and a fraction sign becomes its value. Without this a zero-width space after the
    number, or full-width digits, hides a dose from every pattern below.
    """
    out = []
    for ch in text:
        if ch.isascii():
            out.append(ch)
            continue
        cat = unicodedata.category(ch)
        if cat == "Cf":
            continue
        if "！" <= ch <= "～":
            out.append(chr(ord(ch) - 0xFEE0))
        elif cat == "Nd" and not ("०" <= ch <= "९" or "૦" <= ch <= "૯"):
            out.append(str(unicodedata.digit(ch)))
        elif cat == "No" and unicodedata.numeric(ch, None) is not None:
            out.append(f"{unicodedata.numeric(ch):g}")
        else:
            out.append(ch)
    return "".join(out)


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
    "movento",
    "oberon",
    "takumi",
    "folicur",
    "sectin",
    "acrobat",
    "kocide",
    "ampligo",
    "virtako",
    "alika",
    "ekalux",
    "lesenta",
    "larvin",
    "furadan",
    "thimet",
    "cabrio",
    "targa super",
    "whip super",
    "tata mida",
]
# The same names as written in Devanagari and Gujarati. Not complete. Names that are also
# everyday words (साफ "clean", हमला "attack", कवच "shield") are left out on purpose.
INDIC_BRANDS = [
    "कॉन्फिडोर", "कोन्फिडोर", "कन्फिडोर", "कॉन्फीडोर", "एक्टारा", "अक्तारा", "कोराजन", "ट्रेसर",
    "रिडोमिल", "डाइथेन", "डायथेन", "इंडोफिल", "बाविस्टिन", "राउंडअप", "ग्लाइसेल", "रीजेंट",
    "नुवान", "रोगोर", "मोनोसिल", "उलाला", "पेगासस", "कॉन्टाफ", "ब्लाइटॉक्स", "एमिस्टार",
    "नेटिवो", "एंट्राकोल", "कर्जेट", "प्रोक्लेम", "एडमायर", "मोवेंटो", "ओबेरॉन", "ताकुमी",
    "फोलिक्योर", "फॉलिक्योर", "सेक्टिन", "एक्रोबैट", "कोसाइड", "एम्प्लिगो", "विर्टाको", "अलिका",
    "एकालक्स", "लेसेंटा", "लार्विन", "फ्यूराडान", "फुराडान", "थिमेट", "थाइमेट", "कैब्रियो",
    "टार्गा सुपर", "व्हिप सुपर", "टाटा मिडा",
    "કોન્ફિડોર", "કોન્ફીડોર", "કન્ફિડોર", "એક્ટારા", "અક્તારા", "કોરાજન", "ટ્રેસર", "રિડોમિલ",
    "ડાયથેન", "ઇન્ડોફિલ", "બાવિસ્ટિન", "રાઉન્ડઅપ", "ગ્લાયસેલ", "રીજન્ટ", "રિજેન્ટ", "નુવાન",
    "રોગોર", "મોનોસિલ", "ઉલાલા", "પેગાસસ", "કોન્ટાફ", "બ્લાયટોક્સ", "એમિસ્ટાર", "નેટિવો",
    "એન્ટ્રાકોલ", "કર્ઝેટ", "પ્રોક્લેમ", "એડમાયર", "મોવેન્ટો", "ઓબેરોન", "તાકુમી",
    "ફોલિક્યોર", "સેક્ટિન", "એક્રોબેટ", "કોસાઇડ", "એમ્પ્લિગો", "વિર્ટાકો", "અલિકા",
    "એકાલક્સ", "લેસેન્ટા", "લાર્વિન", "ફ્યુરાડાન", "ફુરાડાન", "થિમેટ", "થાઇમેટ", "કેબ્રિયો",
    "ટાર્ગા સુપર", "વ્હિપ સુપર", "ટાટા મિડા",
]  # fmt: skip
BRAND = re.compile(
    r"\b(?:" + "|".join(BRANDS) + r")s?\b|(?<![ऀ-ॿ઀-૿])(?:" + "|".join(INDIC_BRANDS) + r")",
    re.IGNORECASE,
)

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
    sentence = fold(sentence)
    return bool(QUANTITY.search(sentence)) and bool(CHEMICAL.search(sentence))


def names_brand(sentence: str) -> bool:
    return bool(BRAND.search(fold(sentence)))


# A quantity about seed or water is advice, not a dose: "20 kg seed per acre",
# "2 litres of water per plant". Such a sentence never pairs with a chemical one.
NOT_A_DOSE = re.compile(
    r"\bseeds?\b|\bwater(?:ing)?\b|\birrigat\w*|beej|paani|बीज|पानी|सिंचाई|બીજ|પાણી|પિયત",
    re.IGNORECASE,
)


def _quantity_only(sentence: str) -> bool:
    sentence = fold(sentence)
    return (
        bool(QUANTITY.search(sentence))
        and not CHEMICAL.search(sentence)
        and not NOT_A_DOSE.search(sentence)
    )


def _chemical_only(sentence: str) -> bool:
    # A KVK referral ("before using any chemical, ask your KVK") is advice, not half a dose.
    sentence = fold(sentence)
    return (
        bool(CHEMICAL.search(sentence))
        and not QUANTITY.search(sentence)
        and not KVK.search(sentence)
    )


def split_doses(sentences: list[str]) -> set[int]:
    """Indices of neighbouring sentences that give a dose between them (#40).

    "Mix 2 ml per litre. Use imidacloprid." says the same as one dose sentence, so an
    amount-only sentence next to a chemical-only sentence (either order) is removed as
    a pair. Seed and water quantities are exempt, so seed rate and watering advice stay.
    """
    flagged: set[int] = set()
    # One sentence may sit between the two halves ("Mix 2 ml. Wear gloves. Use imidacloprid.").
    for i in range(len(sentences)):
        for j in (i + 1, i + 2):
            if j >= len(sentences):
                break
            a, b = sentences[i], sentences[j]
            if (_quantity_only(a) and _chemical_only(b)) or (
                _chemical_only(a) and _quantity_only(b)
            ):
                flagged |= {i, j}
    return flagged


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
    lines = [split_sentences(line) for line in answer.splitlines()]
    # Sentences in reading order, so a dose split across two list items is still a pair.
    # A blank line does not break the chain: models often put the amount in its own paragraph.
    drop: set[tuple[int, int]] = set()
    run: list[tuple[int, int]] = []
    for li, sentences in enumerate(lines + [[]]):
        if li == len(lines):
            texts = [lines[i][j] for i, j in run]
            drop |= {run[k] for k in split_doses(texts)}
            run = []
            continue
        run += [(li, j) for j, s in enumerate(sentences) if s.strip()]
    for li, sentences in enumerate(lines):
        gone = {
            j for j, s in enumerate(sentences) if is_dose(s) or names_brand(s) or (li, j) in drop
        }
        kept = [s for j, s in enumerate(sentences) if j not in gone]
        removed += [sentences[j].strip() for j in sorted(gone)]
        new = " ".join(kept).rstrip()
        # A line left with only list markers or table pipes after removal is dropped.
        if gone and not re.search(r"\w", new):
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
