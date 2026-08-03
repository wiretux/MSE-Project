import re

VOWELS = set("aeiouy")
DOUBLE = ("bb", "dd", "ff", "gg", "mm", "nn", "pp", "rr", "tt")
LI_ENDING = set("cdeghkmnrt")

PREFIX_WORDS = sorted(
    ["gener", "commun", "arsen", "past", "univers", "later", "emerg", "organ", "inter"],
    key=len,
)

EXCEPTIONS = {
    "skis": "ski",
    "skies": "sky",
    "idly": "idl",
    "gently": "gentl",
    "ugly": "ugli",
    "early": "earli",
    "only": "onli",
    "singly": "singl",
    "sky": "sky",
    "news": "news",
    "howe": "howe",
    "atlas": "atlas",
    "cosmos": "cosmos",
    "bias": "bias",
    "andes": "andes",
}

STEP_2_RULES = sorted(
    [
        ("tional", "tion"),
        ("enci", "ence"),
        ("anci", "ance"),
        ("abli", "able"),
        ("entli", "ent"),
        ("izer", "ize"),
        ("ization", "ize"),
        ("ational", "ate"),
        ("ation", "ate"),
        ("ator", "ate"),
        ("alism", "al"),
        ("aliti", "al"),
        ("alli", "al"),
        ("fulness", "ful"),
        ("ousli", "ous"),
        ("ousness", "ous"),
        ("iveness", "ive"),
        ("iviti", "ive"),
        ("biliti", "ble"),
        ("bli", "ble"),
        ("ogist", "og"),
        ("fulli", "ful"),
        ("lessli", "less"),
    ],
    key=lambda rule: len(rule[0]),
    reverse=True,
)

STEP_3_RULES = sorted(
    [
        ("tional", "tion"),
        ("ational", "ate"),
        ("alize", "al"),
        ("icate", "ic"),
        ("iciti", "ic"),
        ("ical", "ic"),
        ("ful", ""),
        ("ness", ""),
    ],
    key=lambda rule: len(rule[0]),
    reverse=True,
)

STEP_4_RULES = sorted(
    [
        "al",
        "ance",
        "ence",
        "er",
        "ic",
        "able",
        "ible",
        "ant",
        "ement",
        "ment",
        "ent",
        "ism",
        "ate",
        "iti",
        "ous",
        "ive",
        "ize",
    ],
    key=len,
    reverse=True,
)


def __is_vowel(word: str, index: int = 0) -> bool:
    return word[index] in VOWELS


def __has_vowel(word: str) -> bool:
    return any(__is_vowel(c) for c in word)


def __mark_region(word: str) -> tuple[int, int]:
    r1, r2 = len(word), len(word)

    for prefix in PREFIX_WORDS:
        if word.startswith(prefix):
            r1 = len(prefix)
            break
    else:
        for i in range(1, len(word)):
            if not __is_vowel(word, i) and __is_vowel(word, i - 1):
                r1 = i + 1
                break

    for i in range(r1, len(word)):
        if not __is_vowel(word, i) and __is_vowel(word, i - 1):
            r2 = i + 1
            break

    return r1, r2


def __endswith_short_syllabel(word: str) -> bool:
    # (a) Non-vowel followed by a vowel followed by a non-vowel other than w, x or Y at end of string
    rule_a = rf"[^{VOWELS}][{VOWELS}][^{VOWELS}wxY]$"

    # (b) A vowel at the beginning of the word followed by a non-vowel
    rule_b = rf"^[{VOWELS}][^{VOWELS}]$"

    # (c) Ends with past
    rule_c = r"past$"

    return bool(re.search(rf"{rule_a}|{rule_b}|{rule_c}", word))


def __is_short(word: str, r1: int) -> bool:
    return len(word) == r1 and __endswith_short_syllabel(word)


def porter2_stemmer(word: str) -> str:
    word = word.lower()
    if len(word) <= 2:
        return word

    if word in EXCEPTIONS:
        return EXCEPTIONS[word]

    word = word.removeprefix("'")
    word = re.sub(rf"(^|[{VOWELS}])y", r"\1Y", word)

    # Calculate regions
    r1, r2 = __mark_region(word)

    # Step 0

    word = re.sub(r"\'(s\'?)?$", "", word)

    # Step 1a

    if word.endswith("sses"):
        word = word.removesuffix("sses") + "ss"
    elif word.endswith(("ied", "ies")):
        stem = re.sub(r"ied|ies$", "", word)
        word = stem + ("i" if len(stem) > 1 else "ie")
    elif word.endswith(("us", "ss")):
        pass
    elif word.endswith("s") and __has_vowel(
        word[:-2]
    ):  # any(__is_vowel(c) for c in word[:-2]):
        word = word.removesuffix("s")

    # Step 1b

    if word.endswith(("eedly", "eed")):
        stem = word.removesuffix("ly").removesuffix("eed")
        if len(stem) >= r1:
            word = stem + "ee"
    elif bool(re.search(rf"[^{VOWELS}]ying$", word)):
        word = word.removesuffix("ying") + "ie"
    elif word.endswith(
        ("inning", "outing", "canning", "herring", "earring", "evening")
    ):
        pass
    elif word.endswith(("ed", "edly", "ing", "ingly")):
        stem = re.sub("(ed|edly|ing|ingly)$", "", word)
        if __has_vowel(stem):
            word = stem

            if word.endswith(("at", "bl", "iz")):
                word += "e"
            elif word.endswith(DOUBLE):
                # Contains letter other than a/e/o
                if any(c not in ("a", "e", "o") for c in word[:-2]):
                    word = word[:-1]
            elif __is_short(word, r1):
                word += "e"

    # Step 1c

    # Replace if y/Y is preceded by non vowel, that is not first character
    word = re.sub(rf"(.+[^{VOWELS}])[yY]$", r"\1i", word)

    # Step 2

    for suffix, replacement in STEP_2_RULES:
        if word.endswith(suffix):
            stem = word.removesuffix(suffix)
            if len(stem) >= r1:
                word = stem + replacement
            break
    else:
        if word.endswith("ogi"):
            stem = word.removesuffix("ogi")
            if len(stem) >= r1 and stem[-1] == "l":
                word = stem + "og"
        elif word.endswith("li"):
            stem = word.removesuffix("li")
            if len(stem) >= r1 and stem[-1] in LI_ENDING:
                word = stem

    # Step 3

    for suffix, replacement in STEP_3_RULES:
        if word.endswith(suffix):
            stem = word.removesuffix(suffix)
            if len(stem) >= r1:
                word = stem + replacement
            break
    else:
        if word.endswith("ative"):
            stem = word.removesuffix("ative")
            if len(stem) >= r2:
                word = stem

    # Step 4

    for suffix in STEP_4_RULES:
        if word.endswith(suffix):
            stem = word.removesuffix(suffix)
            if len(stem) >= r2:
                word = stem
            break
    else:
        if word.endswith("ion"):
            stem = word.removesuffix("ion")
            if len(stem) >= r2 and stem[-1] in "st":
                word = stem

    # Step 5

    if word.endswith("e"):
        stem = word.removesuffix("e")
        if len(stem) >= r2 or (len(stem) >= r1 and not __endswith_short_syllabel(stem)):
            word = stem
    elif word.endswith("l"):
        stem = word.removesuffix("l")
        if len(stem) >= r2 and stem[-1] == "l":
            word = stem

    return word.lower()
