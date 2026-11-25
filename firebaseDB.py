import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore


def init():
    if not firebase_admin._apps:
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
    if not globals().get("db"):
        globals()["db"] = firestore.client()


def get_leaderboard():
    init()
    leaderboard = []
    for user in (
        db.collection("users")
        .order_by("score", direction=firestore.Query.DESCENDING)
        .stream()
    ):
        if user.to_dict().get(
            "username"
        ):  # using get() to avoid KeyError (username is not set for all users)
            display_name = user.to_dict()["username"]
        else:
            display_name = user.to_dict()["email"].split("@")[0]

        leaderboard.append(
            {"username": display_name, "score": user.to_dict().get("score")}
        )

    import game

    return game.place_player(leaderboard, None, None)


def getDocumentFor(username_or_email):
    db = getDB()
    users = getUsers()
    for user in users:
        if (
            user.get("username") == username_or_email
            or user.get("email") == username_or_email
        ):
            for document in db.collection("users").get():
                if document.to_dict()["username"] == user["username"]:
                    return document.reference

    return None


def getDocumentDFor(username_or_email):
    db = getDB()
    users = getUsers()
    for user in users:
        if (
            user.get("username") == username_or_email
            or user.get("email") == username_or_email
        ):
            for document in db.collection("users").get():
                if document.to_dict()["username"] == user["username"]:
                    return document

    return None


def getUsers():
    """Get all users from the database"""
    db = getDB()
    users = []
    for user in db.collection("users").get():
        users.append(user.to_dict())
    return users


def getDB():
    init()
    return globals()["db"]


def getScore(username_or_email):
    document = getDocumentFor(username_or_email)
    if document:
        return document.get().to_dict()["score"]
    return None


def setScore(username_or_email, score, overwrite=False):
    document = getDocumentFor(username_or_email)
    if document:
        if overwrite:
            document.update({"score": score})
        else:
            document.update({"score": firestore.Increment(score)})
        return True
    return False


def set_username(email, username):
    document = getDocumentFor(email)
    if not document:
        return False
    document.update({"username": username})
    return True


def delete_user_doc(email):
    document = getDocumentFor(email)
    if not document:
        return False
    document.delete()
    return True


def add_user_to_db(email, username):
    db = getDB()
    users = getUsers()
    for user in users:
        if user["email"] == email:
            return False
    db.collection("users").add(
        {
            "email": email,
            "score": 0,
            "username": username,
            "admin": False,
            "banned": False,
        }
    )
    return True


def ensure_user_doc(email, username):
    """Create a users document for an account that only exists in Firebase Auth.

    Returns True if a document was created, False if one already existed.
    """
    db = getDB()
    for user in getUsers():
        if user.get("email") == email:
            return False
    db.collection("users").add(
        {
            "email": email,
            "score": 0,
            "username": username,
            "legacy": False,
            "admin": False,
            "banned": False,
        }
    )
    return True


def _user_flags(email):
    document = getDocumentFor(email)
    if not document:
        return {}
    return document.get().to_dict() or {}


def is_admin(email):
    return bool(_user_flags(email).get("admin"))


def is_banned(email):
    return bool(_user_flags(email).get("banned"))


def set_admin(email, admin):
    document = getDocumentFor(email)
    if not document:
        return False
    document.update({"admin": bool(admin)})
    return True


def set_banned(email, banned):
    document = getDocumentFor(email)
    if not document:
        return False
    document.update({"banned": bool(banned)})
    return True


def get_site_config():
    snapshot = getDB().collection("config").document("site").get()
    return snapshot.to_dict() if snapshot.exists else {}


def set_site_config(fields):
    getDB().collection("config").document("site").set(fields or {}, merge=True)
    return True


# Bump when gloss sources change so stale negative misses are refetched.
_GLOSS_CACHE_VERSION = "3"


def _gloss_doc_id(language, word):
    """Stable Firestore id for a language+word gloss cache entry."""
    import hashlib
    import re

    language = (language or "en").strip().lower()
    word = (word or "").strip().lower()
    slug = re.sub(
        r"[^a-z0-9]+", "-", f"{language}-{word}-v{_GLOSS_CACHE_VERSION}"
    ).strip("-")[:80]
    digest = hashlib.sha1(
        f"{_GLOSS_CACHE_VERSION}\0{language}\0{word}".encode("utf-8")
    ).hexdigest()[:12]
    return f"{slug}-{digest}" if slug else digest


def get_word_gloss(language, word):
    """Return cached gloss dict or None when this pair was never looked up.

    Cached misses use definition=None so Wiktionary is not hit again.
    """
    doc_id = _gloss_doc_id(language, word)
    snapshot = getDB().collection("word_glosses").document(doc_id).get()
    if not snapshot.exists:
        return None
    return snapshot.to_dict() or {}


def set_word_gloss(language, word, definition):
    """Store a gloss or a negative cache miss for language+word."""
    import time

    language = (language or "en").strip().lower()
    word = (word or "").strip().lower()
    doc_id = _gloss_doc_id(language, word)
    getDB().collection("word_glosses").document(doc_id).set(
        {
            "language": language,
            "word": word,
            "definition": definition,
            "missing": definition is None,
            "updated_at": time.time(),
        }
    )
    return True


def get_room(code):
    snapshot = getDB().collection("rooms").document(code).get()
    return snapshot.to_dict() if snapshot.exists else None


def delete_room(code):
    getDB().collection("rooms").document(code).delete()


def find_player_room(player_id):
    """Return the room this player is already seated in, if any.

    A player may only occupy one lobby at a time. Rooms are few and short-lived,
    so a collection scan is fine.
    """
    import multiplayer

    if not player_id:
        return None
    for snapshot in getDB().collection("rooms").stream():
        room = snapshot.to_dict() or {}
        if multiplayer.is_member(room, player_id):
            return room
    return None


def cleanup_stale_rooms(now=None):
    """Delete empty rooms and rooms that have been idle past the TTL."""
    import multiplayer

    removed = 0
    for snapshot in getDB().collection("rooms").stream():
        room = snapshot.to_dict() or {}
        if multiplayer.is_stale(room, now=now):
            snapshot.reference.delete()
            removed += 1
    return removed


def leave_other_rooms(player_id, keep_code=None):
    """Enforce one lobby per player by removing them from every other room."""
    import multiplayer

    if not player_id:
        return []
    left = []
    for snapshot in getDB().collection("rooms").stream():
        code = snapshot.id
        if keep_code and code == keep_code:
            continue
        room = snapshot.to_dict() or {}
        if not multiplayer.is_member(room, player_id):
            continue
        room, _ = update_room(
            code, lambda current: multiplayer.remove_player(current, player_id)
        )
        if room is not None and not (room.get("players") or []):
            delete_room(code)
            room = None
        left.append((code, room))
    return left


def create_room(host_id, host_name, language, account=None, attempts=5):
    """Store a new room under an unused code. create() fails if the code is taken.

    One lobby per player: an existing seat is reused instead of opening a second room.
    """
    import multiplayer
    from google.api_core.exceptions import AlreadyExists

    cleanup_stale_rooms()
    existing = find_player_room(host_id)
    if existing:
        return existing

    rooms = getDB().collection("rooms")
    for _ in range(attempts):
        code = multiplayer.make_room_code()
        room = multiplayer.new_room(code, host_id, host_name, language, account)
        try:
            rooms.document(code).create(room)
        except AlreadyExists:
            continue
        return room
    raise RuntimeError("could not find a free room code")


def update_room(code, change):
    """Run change(room) -> (room, error) in a transaction so concurrent moves cannot clash."""
    db = getDB()
    ref = db.collection("rooms").document(code)

    @firestore.transactional
    def run(transaction):
        snapshot = ref.get(transaction=transaction)
        if not snapshot.exists:
            return None, "mp_room_missing"
        room, error = change(snapshot.to_dict())
        if not error:
            transaction.set(ref, room)
        return room, error

    return run(db.transaction())


def join_room_db(code, player_id, name, account=None):
    import multiplayer

    return update_room(
        code, lambda room: multiplayer.add_player(room, player_id, name, account)
    )


def start_room_db(code, player_id):
    import multiplayer

    return update_room(code, lambda room: multiplayer.start_room(room, player_id))


def apply_player_guess(code, player_id, letter):
    import multiplayer

    return update_room(code, lambda room: multiplayer.guess(room, player_id, letter))


def leave_room_db(code, player_id):
    import multiplayer

    room, error = update_room(
        code, lambda current: multiplayer.remove_player(current, player_id)
    )
    if not error and room is not None and not (room.get("players") or []):
        delete_room(code)
        return None, None
    return room, error


def skip_turn_db(code, player_id):
    import multiplayer

    return update_room(code, lambda room: multiplayer.skip_turn(room, player_id))


def set_room_language_db(code, player_id, language):
    import multiplayer

    return update_room(
        code, lambda room: multiplayer.set_language(room, player_id, language)
    )
