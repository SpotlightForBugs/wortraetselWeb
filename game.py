import math
import random
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


def reveal(word, letters, status):
    show = set(letters or [])
    if status == "lost":
        show.update(word or "")
    return [ch if ch in show else "" for ch in (word or "")]


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


def drawing_for(wrong, status):
    if status == "won":
        return "/static/assets/won.svg"
    return generate_hangman(min(int(wrong or 0), 9), 1000, 1000)


def generate_hangman(tries, n, m):
    # the svg images are: static/assets/base.svg, static/assets/Hangman1_01_Zeichenflache_1.svg to static/assets/Hangman8_01_Zeichenflache_1.svg, last is called killed.svg
    image_list = [
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
    ]

    image_extension = ".svg"

    if tries > len(image_list) - 1:
        html = f"<h1>YOU SHOULD BE DEAD, MOM...</h1>"

        return html
    return f"/static/assets/{image_list[tries]}{image_extension}"


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
