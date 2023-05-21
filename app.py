import sentry_sdk
from sentry_sdk import last_event_id
from sentry_sdk.integrations.flask import FlaskIntegration
from sentry_sdk.integrations.pure_eval import PureEvalIntegration
import accounts
import game as play_logic
import firebaseDB

sentry_sdk.init(
    dsn="https://7c71cffadff9423a983843ddd3fe96a3@o1363527.ingest.sentry.io/4505154639364096",
    integrations=[
        FlaskIntegration(), PureEvalIntegration(),
    ],

    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for performance monitoring.
    # We recommend adjusting this value in production.
    traces_sample_rate=1.0,
    send_default_pii=True,
    server_name="Hangman@Web",
    environment="web"

)

import os
import random

from flask import Flask, render_template, request, redirect, url_for, session
from flask_wtf.csrf import CSRFProtect

import firebase_admin
from firebase_admin import credentials, auth
from firebase_admin import firestore

app = Flask(__name__)
app.secret_key = os.urandom(24).hex().encode('utf-8').decode('latin-1').encode('utf-8')
csrf = CSRFProtect(app)
allowed_paths = ['/login', '/register', '/users', '/draw', '/session_data']

if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

@app.route('/', methods=['GET', 'POST'])
def game():
    if 'word' not in session:
        session['word'] = play_logic.getRandomWord('de')
        session['letters'] = []
        session['score'] = 0
        session['wrong_guesses'] = 0
    if request.method == "GET":

        if all(letter in session['letters'] for letter in session['word']) and not session['wrong_guesses'] >= 12:
            play_logic.finish_game(session['username'], word=session['word'], wrong_guesses=session['wrong_guesses'],
                                   success=True, all_guesses=session['letters'])
            word = session['word']
            session['word'] = play_logic.getRandomWord('de')
            session['letters'] = []
            session['score'] = 0
            session['wrong_guesses'] = 0
            return redirect('/game/' + word + "/success")

        elif session['wrong_guesses'] >= 12:
            play_logic.finish_game(session['username'], word=session['word'], wrong_guesses=session['wrong_guesses'],
                                   success=False, all_guesses=session['letters'])
            word = session['word']
            session['word'] = play_logic.getRandomWord('de')
            session['letters'] = []
            session['score'] = 0
            session['wrong_guesses'] = 0
            return redirect('/game/' + word)

        return render_template('game.html', leaderboard=firebaseDB.get_leaderboard(),
                               username=accounts.getUsername(session['username'])['username'],
                               drawing=play_logic.generate_hangman(session["wrong_guesses"], 200, 200),
                               letters=[chr(i) for i in range(65, 91)],
                               word=session['word'], letters_guessed=session['letters'], score=session['score'],
                               wrong_guesses=session['wrong_guesses'],
                               status=play_logic.check_game_status(session['word'], session['letters'],
                                                                   session['wrong_guesses']))
    else:
        letter = request.form['letter'].lower()
        print(letter + " " + str(session['letters']))
        if letter not in session['letters']:
            session['letters'].append(letter)
            if letter in session['word']:

                session['score'] += 1
                print(f"The letter {letter} is in the word {session['word']}")
            else:
                session['wrong_guesses'] += 1
        return redirect(url_for('game'))


@app.route('/game/<word>')
def game_over(word):
    return "<h1>(っ °Д °;)っ " + word.capitalize() + "</h1><script>setTimeout(function(){window.location.href = '/';}, " \
                                                   "5000);</script><style>body{background-color: black; color: " \
                                                   "white;}</style> "


@app.route('/game/<word>/success')
def game_success(word):
    return "<h1> O(∩_∩)O </h1><script>setTimeout(function(){window.location.href = '/';}, " \
           "5000);</script><style>body{background-color: black; color: " \
           "white;}</style> "


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:  # If user is already logged in, redirect to game page
        return redirect(url_for('game'))

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        try:
            user = auth.get_user_by_email(email)
            if user:
                auth_user = accounts.login(email, password)
                session['username'] = auth_user
                return redirect(url_for('game'))
        except Exception as e:
            sentry_sdk.capture_exception(e)
            return render_template('login.html', error="Invalid email or password")
    else:
        return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'username' in session:
        return redirect(url_for('game'))

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        username = request.form['username']
        try:
            user = accounts.register(email, password, username)
            if user:
                session['username'] = email
                return redirect(url_for('game'))
        except:
            return render_template('register.html', error="Email already exists")
    else:
        return render_template('register.html')


@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))


@app.before_request
def before_request():
    # Check if the user is not logged in and the requested path is not the login page
    if 'username' not in session and request.path not in allowed_paths:
        return redirect(url_for('login'))
    elif 'username' in session:
        uname = session['username']
        if '@' in uname:
            sentry_sdk.set_user({"email": uname})
        else:
            sentry_sdk.set_user({"username": uname})


@app.errorhandler(500)
def server_error_handler(error):
    print(error)
    return render_template("500.html", sentry_event_id=last_event_id()), 500


if __name__ == '__main__':
    app.run(port=8080, debug=True)