import random

import requests as requests
import zufallsworte as german_words

import firebaseDB

globals()['LANGUAGES'] = ['en', 'de', 'fi']


def isValidLanguage(language):
    return language in getLanguages()


def getLanguages() -> list:
    return globals()['LANGUAGES']


def getRandomWord(language):
    if isValidLanguage(language):
        if language == 'de':
            return german_words.zufallswoerter(1)[0].lower().replace("ä", "ae").replace("ö", "oe").replace("ü",
                                                                                                           "ue").replace(
                "ß", "ss").lower()
        elif language == 'en':
            english_api = "https://random-word-api.herokuapp.com/word?number=1"
            return requests.get(english_api).json()[0].lower()
        elif language == 'fi':
            finnish_word_list = requests.get(
                "https://raw.githubusercontent.com/hugovk/everyfinnishword/master/kaikkisanat.txt").text.split("\n")
            return random.choice(finnish_word_list).lower()


def generate_hangman(tries, n, m):
    canvas_width = n
    canvas_height = m

    # Calculate the size of each cell in the canvas
    cell_width = canvas_width // 7
    cell_height = canvas_height // 12

    # Start building the HTML string
    html = '<canvas width="{}" height="{}"></canvas>'.format(canvas_width, canvas_height)
    html += '<script>'
    html += 'var canvas = document.querySelector("canvas");'
    html += 'var ctx = canvas.getContext("2d");'

    # Draw the hangman figure based on the number of tries left
    if tries >= 0:
        # Draw the scaffold
        html += 'ctx.beginPath();'
        html += 'ctx.moveTo({0}, {1});'.format(cell_width, canvas_height - cell_height)
        html += 'ctx.lineTo({0}, {1});'.format(canvas_width - cell_width, canvas_height - cell_height)
        html += 'ctx.lineTo({0}, {1});'.format(canvas_width - cell_width, cell_height)
        html += 'ctx.lineTo({0}, {1});'.format(canvas_width - 2 * cell_width, cell_height)
        html += 'ctx.stroke();'

        if tries >= 1:
            # Draw the head
            html += 'ctx.beginPath();'
            html += 'ctx.arc({0}, {1}, {2}, 0, Math.PI * 2);'.format(canvas_width - 2 * cell_width,
                                                                     cell_height + 2 * cell_height, cell_height)
            html += 'ctx.stroke();'

            if tries >= 2:
                # Draw the eyes
                html += 'ctx.beginPath();'
                html += 'ctx.arc({0}, {1}, {2}, 0, Math.PI * 2);'.format(
                    canvas_width - 2 * cell_width - 10, cell_height + 2 * cell_height - 5, 2)
                html += 'ctx.stroke();'

                html += 'ctx.beginPath();'
                html += 'ctx.arc({0}, {1}, {2}, 0, Math.PI * 2);'.format(
                    canvas_width - 2 * cell_width + 10, cell_height + 2 * cell_height - 5, 2)
                html += 'ctx.stroke();'

                if tries >= 3:
                    # Draw the mouth
                    html += 'ctx.beginPath();'
                    html += 'ctx.arc({0}, {1}, {2}, Math.PI * 0.25, Math.PI * 0.75, false);'.format(
                        canvas_width - 2 * cell_width, cell_height + 2 * cell_height, 10)
                    html += 'ctx.stroke();'

                    if tries >= 4:
                        # Draw the body
                        html += 'ctx.beginPath();'
                        html += 'ctx.moveTo({0}, {1});'.format(canvas_width - 2 * cell_width,
                                                               cell_height + 3 * cell_height)
                        html += 'ctx.lineTo({0}, {1});'.format(canvas_width - 2 * cell_width,
                                                               cell_height + 7 * cell_height)
                        html += 'ctx.stroke();'

                        if tries >= 5:
                            # Draw the left arm
                            html += 'ctx.beginPath();'
                            html += 'ctx.moveTo({0}, {1});'.format(canvas_width - 2 * cell_width,
                                                                   cell_height + 4 * cell_height)
                            html += 'ctx.lineTo({0}, {1});'.format(canvas_width - 3 * cell_width,
                                                                   cell_height + 6 * cell_height)
                            html += 'ctx.stroke();'

                            if tries >= 6:
                                # Draw the right arm
                                html += 'ctx.beginPath();'
                                html += 'ctx.moveTo({0}, {1});'.format(canvas_width - 2 * cell_width,
                                                                       cell_height + 4 * cell_height)
                                html += 'ctx.lineTo({0}, {1});'.format(canvas_width - cell_width,
                                                                       cell_height + 6 * cell_height)
                                html += 'ctx.stroke();'

                                if tries >= 7:
                                    # Draw the left leg
                                    html += 'ctx.beginPath();'
                                    html += 'ctx.moveTo({0}, {1});'.format(canvas_width - 2 * cell_width,
                                                                           cell_height + 7 * cell_height)
                                    html += 'ctx.lineTo({0}, {1});'.format(canvas_width - 3 * cell_width,
                                                                           canvas_height - cell_height)
                                    html += 'ctx.stroke();'

                                    if tries >= 8:
                                        # Draw the right leg
                                        html += 'ctx.beginPath();'
                                        html += 'ctx.moveTo({0}, {1});'.format(canvas_width - 2 * cell_width,
                                                                               cell_height + 7 * cell_height)
                                        html += 'ctx.lineTo({0}, {1});'.format(canvas_width - cell_width,
                                                                               canvas_height - cell_height)
                                        html += 'ctx.stroke();'

                                        if tries >= 9:
                                            # Draw the left eyebrow
                                            html += 'ctx.beginPath();'
                                            html += 'ctx.moveTo({0}, {1});'.format(
                                                canvas_width - 2 * cell_width - 15, cell_height + 2 * cell_height - 15)
                                            html += 'ctx.lineTo({0}, {1});'.format(
                                                canvas_width - 2 * cell_width - 5, cell_height + 2 * cell_height - 5)
                                            html += 'ctx.stroke();'

                                            if tries >= 10:
                                                # Draw the right eyebrow
                                                html += 'ctx.beginPath();'
                                                html += 'ctx.moveTo({0}, {1});'.format(
                                                    canvas_width - 2 * cell_width + 5,
                                                    cell_height + 2 * cell_height - 5)
                                                html += 'ctx.lineTo({0}, {1});'.format(
                                                    canvas_width - 2 * cell_width + 15,
                                                    cell_height + 2 * cell_height - 15)
                                                html += 'ctx.stroke();'

                                                if tries >= 11:
                                                    # Draw the hat
                                                    html += 'ctx.beginPath();'
                                                    html += 'ctx.moveTo({0}, {1});'.format(
                                                        canvas_width - 2 * cell_width - 20,
                                                        cell_height + 2 * cell_height - 20)
                                                    html += 'ctx.lineTo({0}, {1});'.format(
                                                        canvas_width - 2 * cell_width + 20,
                                                        cell_height + 2 * cell_height - 20)
                                                    html += 'ctx.stroke();'

                                                    if tries >= 12:
                                                        # Draw the "dead" sign
                                                        html += 'ctx.font = "20px Arial";'
                                                        html += 'ctx.fillText("X", {0}, {1});'.format(
                                                            canvas_width - 2 * cell_width - 5,
                                                            cell_height + 2 * cell_height + 5)

    html += '</script>'
    return html


def check_game_status(word, guessed_letters, wrong_tries):
    if wrong_tries >= 12:
        return "lost"
    for letter in word:
        if letter not in guessed_letters:
            return f"Playing: {12 - (wrong_tries)} tries left"
    return f"Won: {word} withing {12 - len(guessed_letters)} tries"


def calculate_points(wrong_guesses: int, word: str, guessed_letters: list, success: bool):
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


def finish_game(username: str, word: str, all_guesses: list, wrong_guesses: int, success: bool):
    points = calculate_points(wrong_guesses, word, all_guesses, success)
    firebaseDB.setScore(username, points)	
