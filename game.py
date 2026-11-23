import random
from pathlib import Path

import requests as requests
import zufallsworte as german_words

globals()["LANGUAGES"] = ["en", "de", "fi", "fr"]

_WORD_LISTS = {}


def _local_words(name):
    if name not in _WORD_LISTS:
        path = Path(__file__).resolve().parent / "data" / f"{name}.txt"
        words = []
        for line in path.read_text(encoding="utf-8").splitlines():
            word = line.strip().lower()
            if len(word) >= 3 and word.isalpha():
                words.append(word)
        _WORD_LISTS[name] = words
    return _WORD_LISTS[name]


def _ascii_word(word):
    return (
        word.lower()
        .replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )


def _remote_lines(url):
    if url in _WORD_LISTS:
        return _WORD_LISTS[url]
    try:
        response = requests.get(url, timeout=8)
        response.raise_for_status()
    except requests.RequestException:
        return []
    lines = [line.strip() for line in response.text.splitlines() if line.strip()]
    if lines:
        _WORD_LISTS[url] = lines
    return lines


def isValidLanguage(language):
    return language in getLanguages()


def getLanguages() -> list:
    return globals()["LANGUAGES"]


def getRandomWord(language):
    if isValidLanguage(language):
        if language == "de":
            return _ascii_word(german_words.zufallswoerter(1)[0])
        if language == "en":
            return random.choice(_local_words("en"))
        if language == "fi":
            finnish_words = _remote_lines(
                "https://raw.githubusercontent.com/hugovk/everyfinnishword/master/kaikkisanat.txt"
            )
            if not finnish_words:
                return random.choice(("kissa", "talo", "omena", "metsa", "koulu"))
            return _ascii_word(random.choice(finnish_words))
        if language == "fr":
            french_words = _remote_lines(
                "https://raw.githubusercontent.com/lorenbrichter/Words/master/Words/fr.txt"
            )
            if not french_words:
                return random.choice(("maison", "jardin", "livre", "soleil", "ecole"))
            translation_table = str.maketrans("éàèùâêîôûç", "eaeuaeiouc")
            return random.choice(french_words).lower().translate(translation_table)


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
