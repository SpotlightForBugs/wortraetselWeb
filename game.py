import random

import requests as requests
import zufallsworte as german_words

import firebaseDB

globals()["LANGUAGES"] = ["en", "de", "fi", "fr"]


def isValidLanguage(language):
    return language in getLanguages()


def getLanguages() -> list:
    return globals()["LANGUAGES"]


def getRandomWord(language):
    if isValidLanguage(language):
        if language == "de":
            return (
                german_words.zufallswoerter(1)[0]
                .lower()
                .replace("ä", "ae")
                .replace("ö", "oe")
                .replace("ü", "ue")
                .replace("ß", "ss")
                .lower()
            )
        if language == "en":
            english_api = "https://random-word-api.vercel.app/api?words=1"
            return requests.get(english_api).json()[0].lower()
        if language == "fi":
            finnish_word_list = requests.get(
                "https://raw.githubusercontent.com/hugovk/everyfinnishword/master/kaikkisanat.txt"
            ).text.split("\n")
            return (
                random.choice(finnish_word_list)
                .lower()
                .replace("ä", "ae")
                .replace("ö", "oe")
                .replace("ü", "ue")
                .replace("ß", "ss")
                .lower()
            )
        if language == "fr":
            french_api = "https://raw.githubusercontent.com/lorenbrichter/Words/master/Words/fr.txt"
            translationTable = str.maketrans("éàèùâêîôûç", "eaeuaeiouc")
            french_api_words = requests.get(french_api).text.lower()
            french_api_words = french_api_words.translate(translationTable).split("\n")
            return random.choice(french_api_words)


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
        html = f'<h1>YOU SHOULD BE DEAD, MOM...</h1>'
    
        return html
    return f'static/assets/{image_list[tries]}{image_extension}' 

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
    firebaseDB.setScore(username, points)
