import random
from pathlib import Path

# Latin-script languages from random-word-api. Chinese is omitted because
# the board only has A-Z.
_LANGUAGES = ("en", "es", "it", "de", "fr", "pt-br", "ro", "tr")
_LANGUAGE_NAMES = {
    "en": "English",
    "es": "Spanish",
    "it": "Italian",
    "de": "German",
    "fr": "French",
    "pt-br": "Portuguese",
    "ro": "Romanian",
    "tr": "Turkish",
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


def _local_words(name):
    if name not in _WORD_LISTS:
        path = Path(__file__).resolve().parent / "data" / f"{name}.txt"
        words = []
        for line in path.read_text(encoding="utf-8").splitlines():
            word = line.strip().lower()
            if len(word) >= 3 and word.isascii() and word.isalpha():
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
