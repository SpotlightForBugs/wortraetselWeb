import sentry_sdk
from sentry_sdk import last_event_id
from sentry_sdk.integrations.flask import FlaskIntegration
from sentry_sdk.integrations.pure_eval import PureEvalIntegration
import accounts
import admin_ops
import cap
import game as play_logic
import i18n
import firebaseDB
import multiplayer
import wiktionary

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
import uuid

from flask import (
    Flask,
    jsonify,
    render_template,
    request,
    redirect,
    url_for,
    session,
    send_from_directory,
)
from flask_wtf.csrf import CSRFProtect
from flask_socketio import SocketIO, emit, join_room, leave_room

from request_utils import client_ip

import firebase_admin
from firebase_admin import credentials, auth
from firebase_admin import firestore

app = Flask(__name__)
app.secret_key = os.environ.get("SECRETKEY")
csrf = CSRFProtect(app)
# Threads, not eventlet: eventlet's monkey-patching does not get along with grpc (Firestore).
socketio = SocketIO(app, async_mode="threading")

if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

try:
    admin_ops.promote_bootstrap_admins()
except Exception as exc:
    with sentry_sdk.new_scope() as scope:
        scope.set_extra("phase", "admin_bootstrap")
        sentry_sdk.capture_exception(exc)


def _wants_json():
    return "application/json" in request.headers.get("Accept", "")


def _language():
    """Use an explicit choice. Otherwise follow the browser until a word is underway."""
    if session.get("language_chosen"):
        return play_logic.coerce_language(session.get("language"))
    detected = i18n.match_accept_language(request.headers.get("Accept-Language"))
    idle = "word" not in session or (
        not session.get("letters")
        and not session.get("wrong_guesses")
        and not session.get("result")
    )
    if idle:
        if session.get("language") != detected:
            session["language"] = detected
            session.pop("word", None)
            session.pop("result", None)
        else:
            session["language"] = detected
        return detected
    return play_logic.coerce_language(session.get("language", detected))


def _warm_gloss(word, language):
    """Prefetch a gloss into Firestore after the first guess; never send it early."""
    if not word:
        return
    socketio.start_background_task(wiktionary.warm, word, language)


def _start_round(language=None):
    if language:
        session["language"] = language
    session.pop("result", None)
    session["word"] = play_logic.getRandomWord(session["language"])
    session["letters"] = []
    session["score"] = 0
    session["wrong_guesses"] = 0


def _ensure_round():
    language = _language()
    if "word" not in session:
        _start_round(language)
    elif session.get("language") != language:
        session["language"] = language
    _settle_round()


def _lookup_score(username, leaderboard):
    if not username:
        return None
    for row in leaderboard or []:
        if row.get("username") == username:
            return row.get("score", 0)
    return None


def _board_score():
    try:
        board = firebaseDB.get_leaderboard() or []
    except Exception:
        return None
    return _lookup_score(session.get("display_name"), board)


def _settle_round():
    if session.get("result"):
        return
    status = play_logic.round_status(
        session.get("word"),
        session.get("letters") or [],
        session.get("wrong_guesses") or 0,
    )
    if status == "playing":
        return
    success = status == "won"
    word = session["word"]
    language = play_logic.coerce_language(session.get("language"))
    points = play_logic.calculate_points(
        session["wrong_guesses"], word, session["letters"], success, language
    )
    offer = False
    if "username" in session:
        if success:
            play_logic.finish_game(
                session["username"],
                word=word,
                wrong_guesses=session["wrong_guesses"],
                success=True,
                all_guesses=session["letters"],
                language=language,
            )
        else:
            play_logic.finish_game(
                session["username"],
                word=word,
                wrong_guesses=session["wrong_guesses"],
                success=False,
                all_guesses=session["letters"],
                legacy_account=accounts.is_legacy(session["username"]),
                language=language,
            )
        before = session.get("shown_score") or 0
        session["shown_score"] = play_logic.score_after_round(
            before, points, _board_score()
        )
    else:
        session["pending_score"] = play_logic.stash_guest_points(
            session.get("pending_score", 0), points
        )
        offer = play_logic.should_offer_save(
            logged_in=False,
            dismissed=session.get("register_dismissed", False),
            solved=success,
        )
        if offer:
            session["register_offer"] = True
    session["result"] = {
        "success": success,
        "word": word,
        "offer": offer,
        "points": points,
    }


def _visible_score():
    logged_in = "username" in session
    if logged_in and "shown_score" not in session:
        found = _board_score()
        if found is not None:
            session["shown_score"] = found
    return play_logic.displayed_score(
        session.get("shown_score"),
        session.get("pending_score"),
        logged_in,
    )


def _score_line(language):
    return i18n.text(language, "score_line", n=_visible_score())


def _payload(leaderboard=None):
    language = session.get("language") or "en"
    logged_in = "username" in session
    if logged_in and "shown_score" not in session and leaderboard is not None:
        found = _lookup_score(session.get("display_name"), leaderboard)
        if found is not None:
            session["shown_score"] = found
    state = i18n.client_state(
        language,
        session.get("word") or "",
        session.get("letters") or [],
        session.get("wrong_guesses") or 0,
        result=session.get("result"),
        pending=session.get("pending_score") or 0,
    )
    guest = "username" not in session
    state["score_line"] = _score_line(language)
    state["shown_score"] = _visible_score()
    state["dark"] = bool(session.get("dark_mode", False))
    state["guest"] = guest
    state["username"] = (
        i18n.text(language, "guest") if guest else (session.get("display_name") or "")
    )
    state["kramli"] = _kramli_state(language)
    state["is_admin"] = bool(session.get("is_admin"))
    state["announcement"] = admin_ops.get_announcement()
    return state


def _kramli_state(language=None):
    language = play_logic.coerce_language(language or session.get("language") or "en")
    show = i18n.kramli_supported(language) and not session.get("kramli_ad_hidden")
    return {
        "show": show,
        "href": f"https://kramli.de/?lang={i18n.kramli_site_lang(language)}&via=hm",
    }


def _require_admin():
    if "username" not in session or not session.get("is_admin"):
        return False
    # Re-check so a revoked admin loses access without waiting for logout.
    if not admin_ops.is_admin_email(session["username"]):
        session["is_admin"] = False
        return False
    return True


def _admin_reply(ok, error=None, **extra):
    language = session.get("language") or "en"
    payload = {"ok": ok}
    payload.update(extra)
    if error:
        payload["error"] = i18n.text(language, error)
        payload["error_key"] = error
    return jsonify(payload)


def _page_context(auth=None, auth_error=None):
    _ensure_round()
    language = session["language"]
    guest = "username" not in session
    if not guest:
        try:
            session["display_name"] = accounts.getUsername(session["username"])[
                "username"
            ]
        except Exception:
            session["display_name"] = session.get("display_name") or session["username"]
        admin_ops.ensure_bootstrap_admin(session["username"])
        session["is_admin"] = admin_ops.is_admin_email(session["username"])
    else:
        session.pop("is_admin", None)
    try:
        leaderboard = firebaseDB.get_leaderboard() or []
    except Exception:
        leaderboard = []
    state = _payload(leaderboard=leaderboard)
    if not guest:
        leaderboard = play_logic.place_player(
            leaderboard, session.get("display_name"), state["shown_score"]
        )
    if auth not in ("login", "register") or not guest:
        auth = None
    return dict(
        copy=state["copy"],
        html_lang=state["html_lang"],
        user_language=language,
        all_languages=play_logic.getLanguages(),
        language_names=play_logic.language_names(),
        language_flag=state["flag"],
        username=state["username"],
        guest=guest,
        dark_mode=state["dark"],
        drawing=state["drawing"],
        letters=[chr(i) for i in range(65, 91)],
        letter_states=state["letter_states"],
        tiles=state["tiles"],
        score_line=state["score_line"],
        leaderboard=leaderboard,
        result=state["result"],
        auth=auth,
        auth_error=auth_error,
        state_json=state,
        kramli=state["kramli"],
        is_admin=bool(session.get("is_admin")),
        announcement=state.get("announcement") or "",
    )


def _remember_player(email, display_name=None):
    session["username"] = email
    admin_ops.ensure_bootstrap_admin(email)
    session["is_admin"] = admin_ops.is_admin_email(email)
    if display_name:
        session["display_name"] = display_name
        return
    try:
        session["display_name"] = accounts.getUsername(email)["username"]
    except Exception:
        session["display_name"] = email.split("@")[0]


@app.route("/", methods=["GET", "POST"])
def game():
    if request.method == "POST":
        _ensure_round()
        if not session.get("result"):
            incoming = (request.form.get("letter") or "").lower()
            before = set(session.get("letters") or [])
            letters, wrong, _status = play_logic.apply_guess(
                session["word"],
                session.get("letters") or [],
                session.get("wrong_guesses") or 0,
                incoming,
            )
            session["letters"] = letters
            session["wrong_guesses"] = wrong
            if not before and letters:
                _warm_gloss(session.get("word"), session.get("language"))
            if (
                len(incoming) == 1
                and incoming.isalpha()
                and incoming not in before
                and incoming in session["word"]
            ):
                session["score"] = session.get("score", 0) + 1
            _settle_round()
        if _wants_json():
            return jsonify(_payload())
        return redirect(url_for("game"))

    auth = request.args.get("auth")
    return render_template("game.html", **_page_context(auth=auth))


@app.route("/set_language", methods=["POST"])
def set_language():
    chosen = request.form.get("language", "")
    if chosen in play_logic.getLanguages():
        session["language_chosen"] = True
        session["language"] = chosen
        _start_round(chosen)
    elif "word" not in session:
        _ensure_round()
    if _wants_json():
        return jsonify(_payload())
    return redirect(url_for("game"))


@app.route("/set_dark_mode", methods=["POST"])
def dark_mode():
    session["dark_mode"] = not session.get("dark_mode", False)
    if _wants_json():
        return jsonify({"dark": session["dark_mode"]})
    return redirect(url_for("game"))


def _clear_offer():
    session.pop("register_offer", None)
    result = session.get("result")
    if not result or not result.get("offer"):
        return
    result = dict(result)
    result["offer"] = False
    session["result"] = result


def _apply_pending_score():
    pending = session.get("pending_score") or 0
    if not pending or "username" not in session:
        return
    before = session.get("shown_score") or 0
    try:
        wrote = firebaseDB.setScore(session["username"], pending)
    except Exception:
        wrote = False
    if not wrote:
        return
    session.pop("pending_score", None)
    session.pop("register_offer", None)
    session["shown_score"] = play_logic.score_after_round(
        before, pending, _board_score()
    )


def _auth_reply(ok, panel, error_key=None):
    language = session.get("language") or i18n.match_accept_language(
        request.headers.get("Accept-Language")
    )
    if ok and _wants_json():
        body = _payload()
        body["ok"] = True
        return jsonify(body)
    if ok:
        return redirect(url_for("game"))
    message = i18n.text(language, error_key or "try_again")
    if _wants_json():
        return jsonify({"ok": False, "error": message})
    return render_template("game.html", **_page_context(auth=panel, auth_error=message))


@app.route("/game/<word>")
@app.route("/game/<word>/success")
def game_result(word):
    return redirect(url_for("game"))


@app.route("/continue", methods=["POST"])
def continue_round():
    _ensure_round()
    _start_round()
    if _wants_json():
        return jsonify(_payload())
    return redirect(url_for("game"))


@app.route("/define", methods=["GET"])
def define_word():
    """Wiktionary gloss for the result screen; empty when nothing useful exists."""
    language = play_logic.coerce_language(
        request.args.get("lang") or session.get("language") or "en"
    )
    word = request.args.get("word") or ""
    gloss = wiktionary.define(word, language)
    return jsonify({"definition": gloss})


@app.route("/login", methods=["GET", "POST"])
def login():
    if "username" in session:
        return redirect(url_for("game"))
    if request.method != "POST":
        return redirect(url_for("game", auth="login"))
    if "language" not in session:
        _ensure_round()
    if not cap.token_ok(request.form.get("cap-token", "")):
        return _auth_reply(False, "login", "cap_error")
    email = request.form.get("email", "")
    password = request.form.get("password", "")
    try:
        user = auth.get_user_by_email(email)
    except Exception:
        return _auth_reply(False, "login", "bad_login")
    if not user:
        return _auth_reply(False, "login", "bad_login")
    if getattr(user, "disabled", False) or firebaseDB.is_banned(email):
        return _auth_reply(False, "login", "admin_banned")
    auth_user = accounts.login(email, password)
    if not auth_user:
        return _auth_reply(False, "login", "session_expired")
    _remember_player(auth_user)
    _clear_offer()
    _apply_pending_score()
    return _auth_reply(True, "login")


@app.route("/register", methods=["GET", "POST"])
def register():
    if "username" in session:
        return redirect(url_for("game"))
    if request.method != "POST":
        return redirect(url_for("game", auth="register"))
    if "language" not in session:
        _ensure_round()
    if request.form.get("password", "") != request.form.get("password2", ""):
        return _auth_reply(False, "register", "password_mismatch")
    if not cap.token_ok(request.form.get("cap-token", "")):
        return _auth_reply(False, "register", "cap_error")
    email = request.form.get("email", "")
    password = request.form.get("password", "")
    username = request.form.get("username", "")
    try:
        user = accounts.register(email, password, username)
    except Exception:
        return _auth_reply(False, "register", "email_exists")
    if not user:
        return _auth_reply(False, "register", "email_exists")
    _remember_player(email, username)
    _clear_offer()
    _apply_pending_score()
    return _auth_reply(True, "register")


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
    _ensure_round()
    _start_round()
    if _wants_json():
        return jsonify(_payload())
    return redirect(url_for("game"))


@app.route("/logout")
def logout():
    session.pop("username", None)
    session.pop("display_name", None)
    session.pop("is_admin", None)
    session.pop("shown_score", None)
    if _wants_json():
        _ensure_round()
        return jsonify(_payload())
    return redirect(url_for("game"))


def _account_reply(ok, error=None, **extra):
    _ensure_round()
    payload = _payload()
    payload.update(extra)
    payload["ok"] = ok
    if error:
        payload["error"] = i18n.text(session["language"], error)
        payload["error_key"] = error
    return jsonify(payload)


@app.route("/account/name", methods=["POST"])
def account_name():
    if "username" not in session:
        return _account_reply(False, "session_expired"), 401
    ok, result = accounts.update_display_name(
        session["username"], request.form.get("username")
    )
    if not ok:
        return _account_reply(False, result)
    session["display_name"] = result
    return _account_reply(True)


@app.route("/account/password", methods=["POST"])
def account_password():
    if "username" not in session:
        return _account_reply(False, "session_expired"), 401
    ok, error = accounts.change_password(
        session["username"],
        request.form.get("current_password"),
        request.form.get("new_password"),
    )
    if not ok:
        return _account_reply(False, error)
    return _account_reply(True)


@app.route("/account/delete", methods=["POST"])
def account_delete():
    if "username" not in session:
        return _account_reply(False, "session_expired"), 401
    ok, error = accounts.delete_account(
        session["username"], request.form.get("password")
    )
    if not ok:
        return _account_reply(False, error)
    session.clear()
    _ensure_round()
    return _account_reply(True)


@app.route("/kramli/dismiss", methods=["POST"])
def kramli_dismiss():
    session["kramli_ad_hidden"] = True
    if _wants_json():
        language = session.get("language") or "en"
        return jsonify({"ok": True, "kramli": _kramli_state(language)})
    return redirect(request.referrer or url_for("game"))


@app.route("/admin/overview", methods=["GET"])
def admin_overview():
    if not _require_admin():
        return _admin_reply(False, "admin_forbidden"), 403
    return _admin_reply(
        True,
        users=admin_ops.list_users(request.args.get("q", "")),
        rooms=admin_ops.list_rooms(),
        announcement=admin_ops.get_announcement(),
    )


@app.route("/admin/users/score", methods=["POST"])
def admin_set_score():
    if not _require_admin():
        return _admin_reply(False, "admin_forbidden"), 403
    ok, result = admin_ops.set_score(
        request.form.get("email"), request.form.get("score")
    )
    if not ok:
        return _admin_reply(False, result)
    return _admin_reply(
        True, score=result, users=admin_ops.list_users(request.form.get("q", ""))
    )


@app.route("/admin/users/rename", methods=["POST"])
def admin_rename_user():
    if not _require_admin():
        return _admin_reply(False, "admin_forbidden"), 403
    ok, result = admin_ops.rename_user(
        request.form.get("email"), request.form.get("username")
    )
    if not ok:
        return _admin_reply(False, result)
    return _admin_reply(
        True, username=result, users=admin_ops.list_users(request.form.get("q", ""))
    )


@app.route("/admin/users/ban", methods=["POST"])
def admin_ban_user():
    if not _require_admin():
        return _admin_reply(False, "admin_forbidden"), 403
    banned = request.form.get("banned", "1") in ("1", "true", "on", "yes")
    ok, result = admin_ops.set_banned(request.form.get("email"), banned)
    if not ok:
        return _admin_reply(False, result)
    return _admin_reply(
        True, banned=result, users=admin_ops.list_users(request.form.get("q", ""))
    )


@app.route("/admin/users/delete", methods=["POST"])
def admin_delete_user():
    if not _require_admin():
        return _admin_reply(False, "admin_forbidden"), 403
    ok, error = admin_ops.delete_user(request.form.get("email"), session["username"])
    if not ok:
        return _admin_reply(False, error)
    return _admin_reply(True, users=admin_ops.list_users(request.form.get("q", "")))


@app.route("/admin/users/admin", methods=["POST"])
def admin_set_admin():
    if not _require_admin():
        return _admin_reply(False, "admin_forbidden"), 403
    make_admin = request.form.get("admin", "1") in ("1", "true", "on", "yes")
    ok, result = admin_ops.set_admin_flag(
        request.form.get("email"), make_admin, session["username"]
    )
    if not ok:
        return _admin_reply(False, result)
    return _admin_reply(
        True, admin=result, users=admin_ops.list_users(request.form.get("q", ""))
    )


@app.route("/admin/rooms/close", methods=["POST"])
def admin_close_room():
    if not _require_admin():
        return _admin_reply(False, "admin_forbidden"), 403
    ok, result = admin_ops.close_room(request.form.get("code"))
    if not ok:
        return _admin_reply(False, result)
    return _admin_reply(True, code=result, rooms=admin_ops.list_rooms())


@app.route("/admin/announcement", methods=["POST"])
def admin_announcement():
    if not _require_admin():
        return _admin_reply(False, "admin_forbidden"), 403
    ok, result = admin_ops.set_announcement(
        request.form.get("message"), session["username"]
    )
    if not ok:
        return _admin_reply(False, result)
    return _admin_reply(True, announcement=result)


def _player_id():
    if "mp_id" not in session:
        session["mp_id"] = uuid.uuid4().hex
    return session["mp_id"]


def _player_name(language, requested=None):
    if "username" in session:
        return session.get("display_name") or session["username"].split("@")[0]
    fallback = f"{i18n.text(language, 'guest')} {_player_id()[:4].upper()}"
    if requested is not None:
        session["guest_name"] = multiplayer.sanitize_name(requested, fallback)
    elif "guest_name" not in session:
        session["guest_name"] = fallback
    return session["guest_name"]


@app.route("/multiplayer/create", methods=["POST"])
def multiplayer_create():
    _ensure_round()
    if "username" not in session:
        # Hosting needs an account; guests can still join with a code.
        return redirect(url_for("game", auth="login"))
    language = request.form.get("language")
    if not play_logic.isValidLanguage(language):
        language = session["language"]
    room = firebaseDB.create_room(
        _player_id(), _player_name(language), language, session.get("username")
    )
    return redirect(url_for("multiplayer_room", code=room["room_code"]))


@app.route("/multiplayer/join", methods=["POST"])
def multiplayer_join():
    _ensure_round()
    language = session.get("language") or "en"
    if "username" not in session:
        _player_name(language, request.form.get("guest_name"))
    code = multiplayer.normalize_code(request.form.get("code"))
    if not multiplayer.valid_code(code):
        return redirect(url_for("game"))
    return redirect(url_for("multiplayer_room", code=code))


@app.route("/multiplayer/<code>")
def multiplayer_room(code):
    _ensure_round()
    language = session["language"]
    code = multiplayer.normalize_code(code)
    _player_id()
    room, error = None, "mp_room_missing"
    # Opening the link only shows the room; the visitor joins with the Join button.
    if multiplayer.valid_code(code):
        room = firebaseDB.get_room(code)
        error = None if room else "mp_room_missing"
    state = multiplayer.public_state(room) if room and not error else None
    page = render_template(
        "multiplayer.html",
        copy=i18n.catalog(language),
        html_lang=i18n.html_lang(language),
        user_language=language,
        kramli=_kramli_state(language),
        dark_mode=bool(session.get("dark_mode", False)),
        room_code=code,
        player_id=session.get("mp_id"),
        language_names=play_logic.language_names(),
        error=error,
        state=state,
        letters=[chr(i) for i in range(65, 91)],
    )
    return page, (200 if state else 404)


def _room_event(handler):
    """Socket handlers run outside Flask's request error handling, so report failures here."""

    def wrapped(data=None):
        try:
            return handler(data or {})
        except Exception as error:
            sentry_sdk.capture_exception(error)
            emit("room_error", {"error": "try_again"})

    wrapped.__name__ = handler.__name__
    return wrapped


def _broadcast(room):
    socketio.emit("room_state", multiplayer.public_state(room), to=room["room_code"])


def _award_room(room):
    """Letter-scores from this round: accounts go to the board, guests stash pending."""
    shares = room["result"].get("shares") or {}
    me = session.get("mp_id")
    for player in room.get("players") or []:
        points = shares.get(player["id"], 0)
        if not points:
            continue
        if player.get("account"):
            try:
                firebaseDB.setScore(player["account"], points)
            except Exception as error:
                sentry_sdk.capture_exception(error)
        elif player["id"] == me:
            session["pending_score"] = play_logic.stash_guest_points(
                session.get("pending_score", 0), points
            )


@socketio.on("watch")
@_room_event
def on_watch(data):
    """Subscribe to live updates. Visitors see the lobby before deciding to join."""
    code = multiplayer.normalize_code(data.get("code"))
    room = firebaseDB.get_room(code) if multiplayer.valid_code(code) else None
    if not room:
        emit("room_error", {"error": "mp_room_missing"})
        return
    join_room(code)
    emit("room_state", multiplayer.public_state(room))


@socketio.on("join")
@_room_event
def on_join(data):
    """Take a seat in the room. Everyone watching sees the new player at once."""
    code = multiplayer.normalize_code(data.get("code"))
    player_id = session.get("mp_id")
    if not player_id or not multiplayer.valid_code(code):
        emit("room_error", {"error": "mp_room_missing"})
        return
    language = play_logic.coerce_language(session.get("language"))
    name = _player_name(
        language, data.get("name") if "username" not in session else None
    )
    left = firebaseDB.leave_other_rooms(player_id, keep_code=code)
    for left_code, left_room in left:
        if left_room:
            _broadcast(left_room)
        else:
            socketio.emit("room_error", {"error": "mp_room_missing"}, to=left_code)
    room, error = firebaseDB.join_room_db(
        code, player_id, name, session.get("username")
    )
    if error:
        emit("room_error", {"error": error})
        return
    join_room(code)
    _broadcast(room)


@socketio.on("start_game")
@_room_event
def on_start_game(data):
    code = multiplayer.normalize_code(data.get("code"))
    room, error = firebaseDB.start_room_db(code, session.get("mp_id"))
    if error:
        emit("room_error", {"error": error})
        return
    _broadcast(room)


@socketio.on("guess")
@_room_event
def on_guess(data):
    code = multiplayer.normalize_code(data.get("code"))
    room, error = firebaseDB.apply_player_guess(
        code, session.get("mp_id"), data.get("letter")
    )
    if error:
        emit("room_error", {"error": error})
        return
    if len(room.get("letters") or []) == 1:
        _warm_gloss(room.get("word"), room.get("language"))
    _broadcast(room)
    if room["state"] == "finished":
        _award_room(room)


@socketio.on("skip_turn")
@_room_event
def on_skip_turn(data):
    code = multiplayer.normalize_code(data.get("code"))
    room, error = firebaseDB.skip_turn_db(code, session.get("mp_id"))
    if error == "mp_too_early":
        # Clocks drift a little between browsers; the next timer tick retries.
        return
    if error:
        emit("room_error", {"error": error})
        return
    _broadcast(room)


@socketio.on("set_language")
@_room_event
def on_set_language(data):
    code = multiplayer.normalize_code(data.get("code"))
    room, error = firebaseDB.set_room_language_db(
        code, session.get("mp_id"), data.get("language")
    )
    if error:
        emit("room_error", {"error": error})
        return
    _broadcast(room)


@socketio.on("leave")
@_room_event
def on_leave(data):
    code = multiplayer.normalize_code(data.get("code"))
    room, error = firebaseDB.leave_room_db(code, session.get("mp_id"))
    leave_room(code)
    if error:
        return True
    if room:
        _broadcast(room)
    else:
        # Last player left and the lobby was deleted.
        socketio.emit("room_error", {"error": "mp_room_missing"}, to=code)
    return True


@app.before_request
def before_request():
    uname = session.get("username")
    ip = client_ip(request)
    if uname and "@" in uname:
        sentry_sdk.set_user({"email": uname, "ip_address": ip})
    elif uname:
        sentry_sdk.set_user({"username": uname, "ip_address": ip})


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
    language = session.get("language") or i18n.match_accept_language(
        request.headers.get("Accept-Language")
    )
    return (
        render_template(
            "500.html",
            sentry_event_id=last_event_id(),
            copy=i18n.catalog(language),
            html_lang=i18n.html_lang(language),
        ),
        500,
    )


if __name__ == "__main__":
    socketio.run(app, port=8080, debug=True)
