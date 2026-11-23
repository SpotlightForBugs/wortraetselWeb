import sentry_sdk
from sentry_sdk import last_event_id
from sentry_sdk.integrations.flask import FlaskIntegration
from sentry_sdk.integrations.pure_eval import PureEvalIntegration
import accounts
import cap
import game as play_logic
import firebaseDB

sentry_sdk.init(
    dsn="https://36685b77d489f469c5f64a85d1839aa3@o4509985277018112.ingest.de.sentry.io/4512480802177104",
    integrations=[
        FlaskIntegration(),
        PureEvalIntegration(),
    ],
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for tracing.
    traces_sample_rate=1.0,
    # Set profile_session_sample_rate to 1.0 to profile 100%
    # of profile sessions.
    profile_session_sample_rate=1.0,
    # Set profile_lifecycle to "trace" to automatically
    # run the profiler when there is an active transaction.
    profile_lifecycle="trace",
    server_name="Hangman@Web",
    environment="web",
)

import os
from html import escape

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    send_from_directory,
)
from flask_wtf.csrf import CSRFProtect, generate_csrf

import firebase_admin
from firebase_admin import credentials, auth
from firebase_admin import firestore

app = Flask(__name__)
app.secret_key = os.environ.get("SECRETKEY")
csrf = CSRFProtect(app)

if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()


@app.route("/", methods=["GET", "POST"])
def game():
    language = play_logic.coerce_language(session.get("language", "de"))
    if session.get("language") != language:
        session["language"] = language
        session.pop("word", None)
    if "word" not in session:
        session["language"] = language
        session["word"] = play_logic.getRandomWord(language)
        session["letters"] = []
        session["score"] = 0
        session["wrong_guesses"] = 0
    if request.method == "GET":
        if (
            all(letter in session["letters"] for letter in session["word"])
            and not session["wrong_guesses"] >= 9
        ):
            word = _close_round(success=True)
            return redirect("/game/" + word + "/success")

        elif session["wrong_guesses"] >= 9:
            word = _close_round(success=False)
            return redirect("/game/" + word)

        guest = "username" not in session
        if guest:
            display_name = "Guest"
        else:
            display_name = accounts.getUsername(session["username"])["username"]
        return render_template(
            "game.html",
            leaderboard=firebaseDB.get_leaderboard(),
            username=display_name,
            guest=guest,
            pending_score=session.get("pending_score", 0),
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
            language_names=play_logic.language_names(),
            language_flag=play_logic.language_flag(session["language"]),
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


def _result_page(message, image_src, offer=False):
    safe_message = escape(message)
    safe_src = escape(image_src, quote=True)
    if offer:
        pending = session.get("pending_score", 0)
        token = escape(generate_csrf(), quote=True)
        extra = (
            f"<p class='gate-lead'>This round is worth {pending}. "
            "Create an account if you want it on the leaderboard.</p>"
            "<a class='signup-cta' href='/register'>Create an account</a>"
            "<form method='post' action='/dismiss_save'>"
            f"<input type='hidden' name='csrf_token' value='{token}'>"
            "<button type='submit' class='btn later'>Not now</button>"
            "</form>"
        )
        follow = ""
    else:
        extra = ""
        follow = (
            "<script>setTimeout(function(){window.location.href='/';},5000);</script>"
        )
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>Hangman</title><link rel='stylesheet' href='/static/style.css'>"
        "</head><body><main class='auth-wrap'><section class='auth-card result-card'>"
        f"<p>{safe_message}</p><img alt='' src='{safe_src}' width='640' height='480'>{extra}"
        f"</section></main>{follow}"
        "</body></html>"
    )


def _close_round(success):
    word = session["word"]
    if "username" in session:
        if success:
            play_logic.finish_game(
                session["username"],
                word=word,
                wrong_guesses=session["wrong_guesses"],
                success=True,
                all_guesses=session["letters"],
            )
        else:
            play_logic.finish_game(
                session["username"],
                word=word,
                wrong_guesses=session["wrong_guesses"],
                success=False,
                all_guesses=session["letters"],
                legacy_account=accounts.is_legacy(session["username"]),
            )
    else:
        points = play_logic.calculate_points(
            session["wrong_guesses"], word, session["letters"], success
        )
        session["pending_score"] = play_logic.stash_guest_points(
            session.get("pending_score", 0), points
        )
        if play_logic.should_offer_save(
            logged_in=False,
            dismissed=session.get("register_dismissed", False),
            solved=success,
        ):
            session["register_offer"] = True
    session["word"] = play_logic.getRandomWord(session["language"])
    session["letters"] = []
    session["score"] = 0
    session["wrong_guesses"] = 0
    return word


def _apply_pending_score():
    pending = session.get("pending_score") or 0
    if not pending or "username" not in session:
        return
    if firebaseDB.setScore(session["username"], pending):
        session.pop("pending_score", None)
        session.pop("register_offer", None)


@app.route("/game/<word>")
def game_over(word):
    return _result_page(
        "Du hast verloren. Das Wort war " + word.capitalize(),
        "/static/assets/killed.svg",
    )


@app.route("/game/<word>/success")
def game_success(word):
    return _result_page(
        "Super, du hast es erraten. Das Wort war " + word.capitalize(),
        "/static/assets/won.svg",
        offer="username" not in session and session.get("register_offer", False),
    )


def _cap_endpoint():
    return cap.endpoint(
        os.environ.get("CAP_SERVER_URL"), os.environ.get("CAP_SITE_KEY")
    )


def _render_auth(template, error=None):
    return render_template(template, error=error, cap_endpoint=_cap_endpoint())


@app.route("/login", methods=["GET", "POST"])
def login():
    if "username" in session:  # If user is already logged in, redirect to game page
        return redirect(url_for("game"))

    if request.method == "POST":
        if not cap.token_ok(request.form.get("cap-token", "")):
            return _render_auth(
                "login.html", error="Confirm you are a person, then try again."
            )
        email = request.form["email"]
        password = request.form["password"]
        try:
            user = auth.get_user_by_email(email)
            print(f"User is {user} with email {email}")
        except:
            return _render_auth("login.html", error="Invalid email or password")
        if user:
            auth_user = accounts.login(email, password)
            if auth_user:
                session["username"] = auth_user
                session.pop("register_offer", None)
                _apply_pending_score()
                return redirect(url_for("game"))
            return _render_auth(
                "login.html",
                error="Your Session has expired. Did you change your password?",
            )

    return _render_auth("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if "username" in session:
        return redirect(url_for("game"))

    if request.method == "POST":
        if not cap.token_ok(request.form.get("cap-token", "")):
            return _render_auth(
                "register.html", error="Confirm you are a person, then try again."
            )
        email = request.form["email"]
        password = request.form["password"]
        username = request.form["username"]
        try:
            user = accounts.register(email, password, username)
            if user:
                session["username"] = email
                session.pop("register_offer", None)
                _apply_pending_score()
                return redirect(url_for("game"))
        except:
            return _render_auth("register.html", error="Email already exists")
    else:
        return _render_auth("register.html")


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


@app.route("/dismiss_save", methods=["POST"])
def dismiss_save():
    session["register_dismissed"] = True
    session.pop("register_offer", None)
    return redirect(url_for("game"))


@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect(url_for("game"))


@app.before_request
def before_request():
    uname = session.get("username")
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
