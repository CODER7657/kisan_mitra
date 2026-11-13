import pytest

from kisan import guard

DOSES = [
    "Spray imidacloprid 17.8 SL at 0.5 ml per litre of water.",
    "| Mancozeb | 2 g/l |",
    "Apply 2 bags of urea per acre.",
    "Use 30-40 kg DAP per hectare at sowing.",
    "दवाओं की मात्रा 2 ग्राम प्रति लीटर रखें।",
    "गेहूं में 50 किलो यूरिया प्रति एकड़ डालें।",
    "દવાનો છંટકાવ 15 લિટરના પંપમાં 30 મિલી કરો.",
    "એકર દીઠ ૫૦ કિલો યુરિયા આપો.",
    "kapas me 200 ml dawai per acre dalo.",
]
NOT_DOSES = [
    "Plant seedlings 60 cm apart.",
    "Irrigate every 10 days in winter.",
    "Use a seed rate of 40 kg per acre.",
    "Sow cumin seeds 1 to 2 cm deep.",
    "Remove infected leaves and burn them.",
    "A copper-based fungicide can help; ask the KVK which one.",
    "ઘઉંમાં 20 દિવસે પિયત આપો.",
    "टमाटर के पौधे 60 सेमी की दूरी पर लगाएं।",
    "મારી સમજણમાં 100% ખાતરી છે.",
]


@pytest.mark.parametrize("s", DOSES)
def test_doses_are_caught(s):
    assert guard.is_dose(s)


@pytest.mark.parametrize("s", NOT_DOSES)
def test_other_quantities_are_kept(s):
    assert not guard.is_dose(s)


def test_brands_are_caught():
    assert guard.names_brand("Confidor works well on whitefly.")
    assert not guard.names_brand("Neem-based sprays can help.")


@pytest.mark.parametrize("brand", guard.BRANDS)
def test_every_latin_brand_is_caught_in_any_case_and_in_the_plural(brand):
    for form in (brand, brand.upper(), brand.title(), brand + "s"):
        assert guard.names_brand(f"Spray {form} on the crop."), form
        assert guard.names_brand(f"({form})"), form


@pytest.mark.parametrize("brand", guard.INDIC_BRANDS)
def test_every_indic_brand_is_caught(brand):
    assert guard.names_brand(f"फसल पर {brand} छिड़कें।")
    assert guard.names_brand(f"પાક પર {brand} છાંટો.")
    # A zero-width joiner inside the name must not hide it.
    assert guard.names_brand(brand[:2] + "\u200d" + brand[2:])


def test_brand_lists_have_no_duplicates_and_cover_both_scripts():
    assert len(set(guard.BRANDS)) == len(guard.BRANDS)
    assert len(set(guard.INDIC_BRANDS)) == len(guard.INDIC_BRANDS)
    devanagari = [b for b in guard.INDIC_BRANDS if "\u0900" <= b[0] <= "\u097f"]
    gujarati = [b for b in guard.INDIC_BRANDS if "\u0a80" <= b[0] <= "\u0aff"]
    assert len(devanagari) + len(gujarati) == len(guard.INDIC_BRANDS)
    assert len(devanagari) >= 45 and len(gujarati) >= 45


@pytest.mark.parametrize(
    "sentence",
    [
        "Remove the spotted leaves and burn them.",
        "The acrobatic climb of the vine needs a support.",
        "Use a super absorbent mulch.",
        "Tata is a company; no product is named here.",
        "खेत को साफ रखें और पानी निकालें।",
        "कीटों का हमला बढ़ने पर अधिकारी से मिलें।",
        "ખેતર સાફ રાખો અને પાણી કાઢો.",
        "",
    ],
)
def test_ordinary_words_are_not_brands(sentence):
    assert not guard.names_brand(sentence)


def test_check_removes_only_dose_sentences_and_adds_kvk():
    r = guard.check(
        "**What to do now**\n- Spray mancozeb 2.5 g per litre. Remove spotted leaves.\n"
        "| Product | Dose |\n| Mancozeb | 2 g/l |",
        "dose of mancozeb?",
    )
    assert "2.5 g" not in r.text and "2 g/l" not in r.text
    assert "Remove spotted leaves." in r.text
    assert "| Product | Dose |" in r.text
    assert len(r.removed) == 2
    assert r.kvk_added and "Krishi Vigyan Kendra" in r.text


def test_no_referral_for_a_question_with_no_chemicals():
    r = guard.check("Irrigate every 10 days.", "How often should I water wheat?")
    assert r.text == "Irrigate every 10 days." and not r.kvk_added and not r.removed


def test_existing_referral_is_not_repeated():
    r = guard.check("Ask your KVK which fungicide to use.", "which fungicide?")
    assert not r.kvk_added


def test_notes_follow_the_language():
    r = guard.check("દવાનો છંટકાવ 15 લિટરના પંપમાં 30 મિલી કરો.", "કેટલી દવા?")
    assert "કૃષિ વિજ્ઞાન કેન્દ્ર" in r.text
    assert guard.script_language("ઘઉંમાં પિયત") == "gu"
    assert guard.script_language("गेहूं की सिंचाई") == "hi"
    assert guard.script_language("wheat irrigation") == "en"


# Edge cases found by mutation testing (setup.cfg, .github/workflows/mutation.yml): each
# pins behaviour a surviving mutant changed without any test noticing.


def test_script_blocks_include_their_first_and_last_code_points():
    assert guard.script_language("\u0a80") == "gu" and guard.script_language("\u0aff") == "gu"
    assert guard.script_language("\u0900") == "hi" and guard.script_language("\u097f") == "hi"


def test_equal_gujarati_and_devanagari_counts_read_as_gujarati():
    assert guard.script_language("क ક") == "gu"


def test_notes_follow_the_answer_language_when_there_is_no_question():
    r = guard.check("गेहूं में 50 किलो यूरिया प्रति एकड़ डालें।")
    assert "कृषि विज्ञान केंद्र" in r.text


def test_an_explicit_language_overrides_the_script():
    r = guard.check("Spray 2 ml mancozeb per litre.", "", "hi")
    assert "कृषि विज्ञान केंद्र" in r.text and "Krishi Vigyan Kendra (KVK) or" not in r.text


def test_lines_after_a_dropped_line_and_indentation_are_kept():
    r = guard.check(
        "- Remove spotted leaves.  \n  - Keep them out of the field.\n| Mancozeb | 2 g/l |\nIrrigate in the morning."
    )
    assert r.text.startswith(
        "- Remove spotted leaves.\n  - Keep them out of the field.\nIrrigate in the morning.\n\n"
    )


# Doses with a unit abbreviated by a dot used to leak: the dot was taken as the end of the
# sentence, so the amount and the chemical were checked apart (found by property tests and
# code review, 2026-11-08). Every one of these must be removed.
@pytest.mark.parametrize(
    "dose",
    [
        "Use 5 kg. urea per acre.",
        "Mix 10 gm. mancozeb in water.",
        "Take 2 lit. of neem oil spray.",
        "Spray 2 ml. of imidacloprid per litre.",
        "Mix 5 m.l. Then add 2 g. per litre of mancozeb.",
        "200 मि.ली. दवा प्रति एकड़ डालें।",
        "2 ली. दवा डालें।",
        "5 ग्रा. मैनकोजेब डालें।",
        "2 कि.ग्रा. यूरिया डालें।",
        "5 મિ.લી. દવા છાંટો.",
        "5 લિ. દવા છાંટો.",
        "5 કિ.ગ્રા. ખાતર નાખો.",
    ],
)
def test_dotted_units_never_split_a_dose(dose):
    result = guard.check(dose)
    assert result.removed, dose
    assert not any(ch.isdigit() for ch in result.text.split("*")[0]), result.text


@pytest.mark.parametrize(
    "harmless",
    [
        "Irrigate every 3 days. Keep 2 acres for cotton.",
        "Sow 20 kg. seed per acre.",
        "5 લીલા પાન પર દવા ન છાંટો.",  # "5 green leaves", not 5 litres
    ],
)
def test_dotted_units_do_not_remove_harmless_numbers(harmless):
    assert guard.check(harmless).removed == []


def test_removed_text_is_an_exact_substring_of_the_answer():
    answer = "Use 5 m.l.  of imidacloprid. Water the field."
    result = guard.check(answer)
    assert result.removed and all(part in answer for part in result.removed)


# A dose split across two sentences (#40): the amount in one, the chemical in the next.
@pytest.mark.parametrize(
    "answer",
    [
        "Mix 2 ml per litre. Use imidacloprid.",
        "Use imidacloprid. Mix 2 ml per litre.",
        "- Mix 2 ml per litre.\n- Spray mancozeb on the leaves.",
        "Apply 2 bags per acre. Use urea.",
        "2 मि.ली. प्रति लीटर मिलाएं। फिर दवा छिड़कें।",
        "પ્રતિ લિટર 2 મિ.લી. ભેળવો. પછી દવા છાંટો.",
    ],
)
def test_a_dose_split_across_two_sentences_is_removed(answer):
    result = guard.check(answer)
    assert len(result.removed) == 2, result.removed
    assert not any(ch.isdigit() for ch in result.text.split("*")[0]), result.text


@pytest.mark.parametrize(
    "answer",
    [
        "Use 20 kg seed per acre. Treat the seed with a fungicide.",
        "प्रति एकड़ 20 किलो बीज बोएं। बीज को फफूंदनाशक से उपचारित करें।",
        "Give each plant 2 litres of water. Avoid spraying pesticide at noon.",
        "દરેક છોડને 2 લિટર પાણી આપો. બપોરે દવા ન છાંટો.",
        "Irrigate every 3 days. Ask your KVK about fungicide.",
        "Keep plants 30 cm apart. Remove the spotted leaves.",
        "40 kg per acre. Before using any chemical, confirm with your KVK.",
        "Mix 2 ml per litre.\n\nAsk your KVK which fungicide to use.",
    ],
)
def test_seed_water_spacing_and_kvk_referrals_are_not_paired(answer):
    assert guard.check(answer).removed == []


def test_split_doses_pairs_across_one_sentence_but_no_further():
    near = ["Mix 2 ml per litre.", "Wear gloves.", "Use imidacloprid."]
    assert guard.split_doses(near) == {0, 2}
    far = ["Mix 2 ml per litre.", "Wear gloves.", "Wash your hands.", "Use imidacloprid."]
    assert guard.split_doses(far) == set()


HIDDEN_DOSES = [
    "Spray imidacloprid 10\u200b ml per pump.",  # zero-width space after the number
    "Spray imidacloprid 1\u200d0 m\u00adl per pump.",  # joiner and soft hyphen inside
    "Spray imidacloprid \uff11\uff10 \uff4d\uff4c per pump.",  # full-width digits and letters
    "mancozeb \u0662 ml per litre",  # Arabic-Indic digit
    "mancozeb \u00bd ml per litre",  # fraction sign
    "mancozeb 1/2 ml per litre",
    "Mix ten ml of imidacloprid per pump.",
    "Add a few drops of imidacloprid.",
    "इमिडाक्लोप्रिड दस मिली प्रति पंप डालें।",
    "દવા બે મિલી નાખો",
    "imidacloprid 500 mg per litre",
    "imidacloprid 2 oz per tank",
    "imidacloprid 1 tsp per litre",
    "Add 1 cap of imidacloprid",
    "imidacloprid 10mls",
    "mancozeb 0.2 percent",
    "Dilute mancozeb 1:500.",
]


@pytest.mark.parametrize("s", HIDDEN_DOSES)
def test_hidden_and_spelled_out_doses_are_removed(s):
    result = guard.check(s)
    assert result.removed == [s]
    assert s not in result.text


@pytest.mark.parametrize(
    "s",
    [
        "Spray in the morning between 6:30 and 9:00, never at noon.",
        "One of the leaves shows the fungicide burn.",
        "દવા છાંટતી વખતે એક માણસ સાથે રાખો.",
        "खेत साफ रखें और दवा से पहले KVK से पूछें।",
        "કપાસમાં જીવાતનો હમલો દેખાય તો દવા માટે KVK ને પૂછો.",
    ],
)
def test_number_words_times_and_everyday_words_are_kept(s):
    assert guard.check(s).removed == []


@pytest.mark.parametrize(
    "s",
    [
        "Use Confidors now.",
        "Use Con\u200bfidor now.",
        "કોન્ફિડોર વાપરો.",
        "कन्फिडोर का छिड़काव करें।",
        "એક્ટારાનો ઉપયોગ કરો.",
    ],
)
def test_brands_in_plural_hidden_and_indic_script_are_removed(s):
    assert guard.check(s).removed == [s]


def test_a_dose_in_its_own_paragraph_is_removed_with_its_chemical():
    result = guard.check("Use imidacloprid.\n\n10 ml per pump.\n\nKeep the field clean.")
    assert result.removed == ["Use imidacloprid.", "10 ml per pump."]
    assert "Keep the field clean." in result.text


def test_fold_leaves_ordinary_text_alone():
    for s in ["Plain ASCII, 10 ml.", "દવાનો છંટકાવ ૩૦ મિલી", "दवा २ ग्राम"]:
        assert guard.fold(s) == s
    assert guard.split_doses(["Mix 2 ml per litre.", "Use imidacloprid."]) == {0, 1}
