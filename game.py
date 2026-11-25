import math
import random
import re
import unicodedata
from pathlib import Path

# Latin-script languages from random-word-api. Chinese is omitted because
# the board only has A-Z.
_LANGUAGES = ("en", "es", "it", "de", "fr", "pt-br", "ro", "tr")
_LANGUAGE_NAMES = {
    "en": "English",
    "es": "Español",
    "it": "Italiano",
    "de": "Deutsch",
    "fr": "Français",
    "pt-br": "Português",
    "ro": "Română",
    "tr": "Türkçe",
}
_LANGUAGE_FLAGS = {
    "en": "GB",
    "es": "ES",
    "it": "IT",
    "de": "DE",
    "fr": "FR",
    "pt-br": "BR",
    "ro": "RO",
    "tr": "TR",
}
_WORD_LISTS = {}
_DISPLAY_WORDS = {}
_LETTER_RATES = {}
# Hit payout scales with how rare the letter is in that language's word list.
_LETTER_VALUE_FLOOR = 5
_LETTER_VALUE_CAP = 90
_LETTER_VALUE_SCALE = 15
_LETTER_FOLDS = str.maketrans(
    {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "ß": "ss",
        "æ": "ae",
        "ø": "oe",
        "å": "aa",
        "œ": "oe",
        "ı": "i",
        "ğ": "g",
        "ş": "s",
        "ș": "s",
        "ţ": "t",
        "ț": "t",
        "ñ": "n",
        "ç": "c",
    }
)


def normalize_word(raw):
    """Return one A-Z hangman word, or None when the entry is not a word.

    The word dump includes phrases and UI strings such as "Das ist ein Traum".
    Anything with spaces, quotes, or other non-letters is dropped.
    German umlauts fold to ae/oe/ue/ss so the A-Z board can still spell them.
    """
    if not isinstance(raw, str) or any(ch.isspace() for ch in raw):
        return None
    text = raw.strip().lower().translate(_LETTER_FOLDS)
    if not text:
        return None
    text = "".join(
        ch
        for ch in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(ch)
    )
    if not 3 <= len(text) <= 40 or not text.isascii() or not text.isalpha():
        return None
    return text


def _local_words(name):
    if name not in _WORD_LISTS:
        path = Path(__file__).resolve().parent / "data" / f"{name}.txt"
        words = []
        display = {}
        seen = set()
        for line in path.read_text(encoding="utf-8").splitlines():
            raw = line.strip()
            word = normalize_word(raw)
            if not word or word in seen:
                continue
            seen.add(word)
            words.append(word)
            # Keep diacritics from the dump; play form is always folded lowercase.
            # Casing for reveal is applied in display_word (German nouns, etc.).
            shown = raw
            if shown != word:
                display[word] = shown
        if not words:
            raise ValueError(f"no hangman words for {name}")
        _WORD_LISTS[name] = words
        _DISPLAY_WORDS[name] = display
    return _WORD_LISTS[name]


# Play-form digraphs produced by normalize_word, restored only when the
# word list actually used the matching umlaut/eszett.
_DIGRAPH_DISPLAY = {
    "ae": "ä",
    "oe": "ö",
    "ue": "ü",
    "ss": "ß",
}


def display_word(language, word):
    """Spelling shown when a round ends.

    Restores umlauts from the word list. German nouns are capitalized for
    the reveal line even though the dump is stored lowercase; other
    languages keep the list casing (typically lowercase lemmas).
    """
    language = coerce_language(language)
    play = (word or "").lower()
    if not play:
        return ""
    _local_words(language)
    shown = _DISPLAY_WORDS.get(language, {}).get(play, play)
    if language == "de" and shown:
        shown = shown[:1].upper() + shown[1:]
    return shown


def display_segments(language, word):
    """Align play-form letters with display glyphs (ae/oe/ue/ss → umlaut).

    Each item is ``(play_span, glyph)``. Digraph spans collapse to one
    tile so the board matches the real spelling length.
    """
    play = (word or "").lower()
    if not play:
        return []
    language = coerce_language(language)
    _local_words(language)
    shown = _DISPLAY_WORDS.get(language, {}).get(play, play).lower()
    if shown == play:
        return [(ch, ch) for ch in play]

    segments = []
    i = j = 0
    while i < len(play) and j < len(shown):
        dig = play[i : i + 2]
        if len(dig) == 2 and _DIGRAPH_DISPLAY.get(dig) == shown[j]:
            segments.append((dig, shown[j]))
            i += 2
            j += 1
            continue
        if play[i] == shown[j]:
            segments.append((play[i], shown[j]))
            i += 1
            j += 1
            continue
        # List/play mismatch: keep the play letter visible as itself.
        segments.append((play[i], play[i]))
        i += 1
        j += 1
    while i < len(play):
        segments.append((play[i], play[i]))
        i += 1
    return segments


def isValidLanguage(language):
    return language in getLanguages()


def getLanguages() -> list:
    return list(_LANGUAGES)


def language_names():
    return dict(_LANGUAGE_NAMES)


def language_flag(language):
    return _LANGUAGE_FLAGS.get(coerce_language(language), "GB")


def coerce_language(language):
    if language in _LANGUAGES:
        return language
    return "en"


def getRandomWord(language):
    return random.choice(_local_words(coerce_language(language)))


def letter_rates(language):
    """Share of each A-Z letter across the language's hangman word list."""
    language = coerce_language(language)
    if language not in _LETTER_RATES:
        counts = {chr(c): 0 for c in range(97, 123)}
        total = 0
        for word in _local_words(language):
            for ch in word:
                if ch in counts:
                    counts[ch] += 1
                    total += 1
        if not total:
            _LETTER_RATES[language] = {ch: 1 / 26 for ch in counts}
        else:
            _LETTER_RATES[language] = {
                ch: (counts[ch] / total) if counts[ch] else (0.5 / total)
                for ch in counts
            }
    return _LETTER_RATES[language]


def letter_value(language, letter):
    """Points a correct guess of this letter is worth in this language.

    Rarer letters in the language's dictionary pay more. The value is the
    inverse of the letter's rate versus a uniform 1/26 baseline, clamped so
    common letters stay readable and rare ones do not explode the score.
    """
    letter = (letter or "").lower()
    if len(letter) != 1 or not letter.isalpha():
        return _LETTER_VALUE_FLOOR
    rate = letter_rates(language).get(letter) or (1 / 26)
    uniform = 1 / 26
    return max(
        _LETTER_VALUE_FLOOR,
        min(_LETTER_VALUE_CAP, round(_LETTER_VALUE_SCALE * (uniform / rate))),
    )


def score_guess(language, word, letter):
    """Points for one guess: +value×hits, or a transparent miss based on value."""
    letter = (letter or "").lower()
    value = letter_value(language, letter)
    count = (word or "").count(letter)
    if count:
        return value * count
    # Missing a rare letter costs more; the value table stays the one source of truth.
    return -max(_LETTER_VALUE_FLOOR, value // 4)


def calculate_points(
    wrong_guesses: int, word: str, guessed_letters: list, success: bool, language="en"
):
    """Sum of per-letter scores for the round in this language."""
    points = 0
    for letter in guessed_letters or []:
        points += score_guess(language, word, letter)
    return points


def letter_values(language):
    """A-Z point table for the UI so scoring stays visible."""
    return {chr(c).upper(): letter_value(language, chr(c)) for c in range(97, 123)}


def apply_guess(word, letters, wrong_guesses, letter):
    """Return the board after one guess. A repeated or empty guess changes nothing."""
    letters = [ch.lower() for ch in letters or []]
    wrong_guesses = int(wrong_guesses or 0)
    guess = (letter or "").lower()
    if len(guess) == 1 and guess.isalpha() and guess not in letters:
        letters.append(guess)
        if guess not in (word or ""):
            wrong_guesses += 1
    return letters, wrong_guesses, round_status(word, letters, wrong_guesses)


def round_status(word, letters, wrong_guesses):
    if int(wrong_guesses or 0) >= 9:
        return "lost"
    if word and all(ch in letters for ch in word):
        return "won"
    return "playing"


def reveal(word, letters, status, language=None):
    """Tile glyphs for the board.

    When ``language`` is set, digraphs that map to a real umlaut/eszett in
    the word list collapse to one tile (and one blank) so e.g. ``ue``
    becomes ``ü`` once both letters are known.
    """
    show = set(letters or [])
    if status == "lost":
        show.update(word or "")
    if not language:
        return [ch if ch in show else "" for ch in (word or "")]
    tiles = []
    for span, glyph in display_segments(language, word):
        if all(ch in show for ch in span):
            tiles.append(glyph)
        else:
            tiles.append("")
    return tiles


def letter_states(letters, word):
    guessed = set(letters or [])
    word = word or ""
    states = {}
    for code in range(65, 91):
        lower = chr(code).lower()
        if lower not in guessed:
            states[chr(code)] = "open"
        elif lower in word:
            states[chr(code)] = "hit"
        else:
            states[chr(code)] = "miss"
    return states


# Hangman frames under static/assets/; served via /drawing/<name>.svg so
# dark mode can recolor ink without CSS-filter invert on the <img>.
_HANGMAN_FRAMES = (
    "base",
    "Hangman1_01_Zeichenflache_1",
    "Hangman2_01_Zeichenflache_1",
    "Hangman3_01_Zeichenflache_1",
    "Hangman4_01_Zeichenflache_1",
    "Hangman5_01_Zeichenflache_1",
    "Hangman6_01_Zeichenflache_1",
    "Hangman7_01_Zeichenflache_1",
    "Hangman8_01_Zeichenflache_1",
    "killed",
)
_HANGMAN_WON = "won"
_HANGMAN_ASSETS = frozenset(_HANGMAN_FRAMES + (_HANGMAN_WON,))
_DARK_INK = "#e8eef4"
_DARK_ACCENT = "#ff5c5c"


def drawing_asset_name(wrong, status):
    if status == "won":
        return _HANGMAN_WON
    tries = min(int(wrong or 0), len(_HANGMAN_FRAMES) - 1)
    return _HANGMAN_FRAMES[tries]


def drawing_for(wrong, status, dark=False):
    name = drawing_asset_name(wrong, status)
    url = f"/drawing/{name}.svg"
    if dark:
        url += "?theme=dark"
    return url


def hangman_svg_path(name):
    """Filesystem path for a hangman SVG asset, or None if unknown."""
    if name not in _HANGMAN_ASSETS:
        return None
    return Path(__file__).resolve().parent / "static" / "assets" / f"{name}.svg"


def theme_hangman_svg(svg_text, dark=False):
    """Retint hangman SVG ink for dark mode (not a CSS invert).

    Black strokes/fills become light ink; the red accent stays a clear red.
    Class rules (``.st2``, ``fill:none``) still override the injected path fill.
    """
    if not dark or not svg_text:
        return svg_text
    themed = svg_text.replace("stroke:#000", f"stroke:{_DARK_INK}")
    themed = themed.replace("fill:#fc0000", f"fill:{_DARK_ACCENT}")
    inject = f"path{{fill:{_DARK_INK}}}"
    if inject not in themed:
        themed = re.sub(r"(<style[^>]*>)", rf"\1{inject}", themed, count=1)
    return themed


def generate_hangman(tries, n, m):
    # Kept for callers that still pass width/height; theme via drawing_for.
    del n, m
    return drawing_for(tries, "playing", dark=False)


def check_game_status(word, guessed_letters, wrong_tries):
    if wrong_tries >= 9:
        return "lost"
    for letter in word:
        if letter not in guessed_letters:
            return f"Playing: {9 - (wrong_tries)} tries left"
    return f"Won: {word} withing {9 - len(guessed_letters)} tries"


def should_offer_save(logged_in, dismissed, solved):
    """Ask a guest to register once, after they solve a word."""
    if logged_in or dismissed:
        return False
    return bool(solved)


def stash_guest_points(pending, points):
    return (pending or 0) + points


def displayed_score(saved, pending, logged_in):
    """One score: a guest's finished rounds, or the saved total plus anything not written yet."""
    saved = int(saved or 0)
    pending = int(pending or 0)
    if logged_in:
        return saved + pending
    return pending


def score_number(value):
    """A board cell has to be a number. Labels and blanks become zero."""
    if isinstance(value, bool) or value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip().replace(" ", "")
    if text.lstrip("-").isdigit():
        return int(text)
    return 0


def place_player(rows, name, score):
    """One row per name, ordered by the numeric score."""
    merged = {}
    for row in rows or []:
        label = (row.get("username") or "").strip()
        if not label:
            continue
        points = score_number(row.get("score"))
        merged[label] = max(merged.get(label, points), points)
    player = (name or "").strip()
    if player:
        merged[player] = score_number(score)
    placed = [{"username": label, "score": points} for label, points in merged.items()]
    placed.sort(key=lambda row: (-row["score"], row["username"].casefold()))
    return placed


def score_after_round(saved, points, board_score):
    """Keep the local total when the board has not caught up to this round."""
    saved = int(saved or 0)
    points = int(points or 0)
    if board_score is None or int(board_score) == saved:
        return saved + points
    return int(board_score)


def finish_game(
    username: str,
    word: str,
    all_guesses: list,
    wrong_guesses: int,
    success: bool,
    legacy_account=False,
    language="en",
):
    points = calculate_points(wrong_guesses, word, all_guesses, success, language)
    import firebaseDB

    firebaseDB.setScore(username, points)
