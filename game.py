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
        seen = set()
        for line in path.read_text(encoding="utf-8").splitlines():
            word = normalize_word(line)
            if word and word not in seen:
                seen.add(word)
                words.append(word)
        if not words:
            raise ValueError(f"no hangman words for {name}")
        _WORD_LISTS[name] = words
    return _WORD_LISTS[name]


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


def calculate_points(
    wrong_guesses: int, word: str, guessed_letters: list, success: bool
):
    points = 0

    if success:
        points = 1000 - (wrong_guesses * 100)
    else:
        percentage = 0
        for letter in word:
            if letter not in guessed_letters:
                percentage += 1
        percentage = percentage / len(word) * 100
        points = int(percentage) * -1

    return points


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


def place_player(rows, name, score):
    """Put this player's current score on the board."""
    placed = [dict(row) for row in rows or []]
    if not name:
        return placed
    for row in placed:
        if row.get("username") == name:
            row["score"] = score
            break
    else:
        placed.append({"username": name, "score": score})
    placed.sort(key=lambda row: row.get("score") or 0, reverse=True)
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
):
    points = calculate_points(wrong_guesses, word, all_guesses, success)
    import firebaseDB

    firebaseDB.setScore(username, points)
