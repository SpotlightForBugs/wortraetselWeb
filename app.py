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
        FlaskIntegration(),
        PureEvalIntegration(),
    ],
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for performance monitoring.
    # We recommend adjusting this value in production.
    traces_sample_rate=1.0,
    send_default_pii=True,
    server_name="Hangman@Web",
    environment="web",
)

import os

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    send_from_directory,
)
from flask_wtf.csrf import CSRFProtect

import firebase_admin
from firebase_admin import credentials, auth
from firebase_admin import firestore

app = Flask(__name__)
app.secret_key = os.environ.get("SECRETKEY")
csrf = CSRFProtect(app)
allowed_paths = [
    "/login",
    "/register",
    "/users",
    "/draw",
    "/session_data",
    "/favicon.ico",
    "/robots.txt",
    "/demo",
    "/register_split",
]

if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()


@app.route("/", methods=["GET", "POST"])
def game():
    if "word" not in session:
        if "language" not in session:
            session["language"] = "de"
        session["word"] = play_logic.getRandomWord(session["language"])
        session["letters"] = []
        session["score"] = 0
        session["wrong_guesses"] = 0
    if request.method == "GET":
        if (
            all(letter in session["letters"] for letter in session["word"])
            and not session["wrong_guesses"] >= 9
        ):
            play_logic.finish_game(
                session["username"],
                word=session["word"],
                wrong_guesses=session["wrong_guesses"],
                success=True,
                all_guesses=session["letters"],
            )
            word = session["word"]
            session["word"] = play_logic.getRandomWord(session["language"])
            session["letters"] = []
            session["score"] = 0
            session["wrong_guesses"] = 0
            return redirect("/game/" + word + "/success")

        elif session["wrong_guesses"] >= 9:
            play_logic.finish_game(
                session["username"],
                word=session["word"],
                wrong_guesses=session["wrong_guesses"],
                success=False,
                all_guesses=session["letters"],
                legacy_account=accounts.is_legacy(session["username"]),
            )
            word = session["word"]
            session["word"] = play_logic.getRandomWord(session["language"])
            session["letters"] = []
            session["score"] = 0
            session["wrong_guesses"] = 0
            return redirect("/game/" + word)

        return render_template(
            "game.html",
            leaderboard=firebaseDB.get_leaderboard(),
            username=accounts.getUsername(session["username"])["username"],
            drawing=play_logic.generate_hangman(session["wrong_guesses"], 1000, 1000),
            letters=[chr(i) for i in range(65, 91)],
            word=session["word"],
            letters_guessed=session["letters"],
            score=session["score"],
            wrong_guesses=session["wrong_guesses"],
            status=play_logic.check_game_status(
                session["word"], session["letters"], session["wrong_guesses"]
            ),
            user_language=session["language"],
            all_languages=play_logic.getLanguages(),
            dark_mode=session.get("dark_mode", False),
        )
    if request.method == "POST":
        letter = request.form["letter"].lower()
        print(letter + " " + str(session["letters"]))
        if letter not in session["letters"]:
            session["letters"].append(letter)
            if letter in session["word"]:
                session["score"] += 1
                print(f"The letter {letter} is in the word {session['word']}")
            else:
                session["wrong_guesses"] += 1
        return redirect(url_for("game"))
    return redirect(url_for("login"))


@app.route("/demo")
def demo():
    return render_template("demo.html")


@app.route("/set_language", methods=["POST"])
def set_language():
    if (
        request.method == "POST"
        and "language" in request.form
        and request.form["language"] in play_logic.getLanguages()
    ):
        session["language"] = request.form["language"]
        # reset the game
        session["word"] = play_logic.getRandomWord(session["language"])
        session["letters"] = []
        session["score"] = 0
        session["wrong_guesses"] = 0

    return redirect(url_for("game"))


@app.route("/set_dark_mode", methods=["POST"])
def dark_mode():
    if request.method == "POST" and "dark_mode" in request.form:
        if session.get("dark_mode", False):
            session["dark_mode"] = False
        else:
            session["dark_mode"] = True
    return redirect(url_for("game"))


@app.route("/game/<word>")
def game_over(word):
    with open("static/assets/killed.svg", "r") as killed_image:
        killed_image = killed_image.read()

        return (
            "<p style='font-size: 50px; color: red;'>Du hast verloren. Das Wort war "
            + word.capitalize()
            + "</p>"
            + killed_image
            + "<script>setTimeout(function(){window.location.href = '/';}, "
            "5000);</script>"
        )


@app.route("/game/<word>/success")
def game_success(word):
    return (
        "<h1> Super, du hast es erraten. Das Wort war "
        + word.capitalize()
        + " </h1><script>setTimeout(function(){window.location.href = '/';}, "
        "5000);</script><style>body{background-color: beige; color: "
        "white;}</style>"
        + "<img src='/static/assets/won.svg' width='1000' height='1000'>"
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if "username" in session:  # If user is already logged in, redirect to game page
        return redirect(url_for("game"))

    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        try:
            user = auth.get_user_by_email(email)
            print(f"User is {user} with email {email}")
        except:
            return render_template("login.html", error="Invalid email or password")
        if user:
            auth_user = accounts.login(email, password)
            if auth_user:
                session["username"] = auth_user
                return redirect(url_for("game"))
            return render_template(
                "login.html",
                error="Your Session has expired. Did you change your password?",
            )

    else:
        return render_template("login.html", error="Invalid email or password")


@app.route("/register", methods=["GET", "POST"])
def register():
    if "username" in session:
        return redirect(url_for("game"))

    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        username = request.form["username"]
        try:
            user = accounts.register(email, password, username)
            if user:
                session["username"] = email
                return redirect(url_for("game"))
        except:
            return render_template("register.html", error="Email already exists")
    else:
        return render_template("register.html")


@app.route("/register_split", methods=["GET", "POST"])
def register_split():
    if request.method == "POST":
        if "uname" not in session:
            session["uname"] = request.form.get("username", False)
        if "username" not in session:
            session["username"] = request.form.get("email", False)
        if (
            "password" not in session
            and request.form.get("password")
            and request.form.get("password") != ""
        ):
            session["password"] = request.form.get("password", False)

    return render_template(
        "register_split.html",
        username=session.get("uname", False),
        email=session.get("username", False),
        password=session.get("password", False),
    )


@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect(url_for("login"))


@app.before_request
def before_request():
    # Check if the user is not logged in and the requested path is not the login page
    if "username" not in session and request.path not in allowed_paths:
        return redirect(url_for("login"))
    if "username" in session:
        uname = session["username"]
        if uname and "@" in uname:
            sentry_sdk.set_user({"email": uname})
        elif uname:
            sentry_sdk.set_user({"username": uname})


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, "static"),
        "favicon.ico",
        mimetype="image/vnd.microsoft.icon",
    )


@app.errorhandler(500)
def server_error_handler(error):
    print(error)
    return render_template("500.html", sentry_event_id=last_event_id()), 500


if __name__ == "__main__":
    app.run(port=8080, debug=True)
