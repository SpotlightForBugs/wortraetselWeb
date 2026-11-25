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


def add_user_to_db(email, username):
    db = getDB()
    users = getUsers()
    for user in users:
        if user["email"] == email:
            return False
    db.collection("users").add({"email": email, "score": 0, "username": username})
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
        {"email": email, "score": 0, "username": username, "legacy": False}
    )
    return True


def get_room(code):
    snapshot = getDB().collection("rooms").document(code).get()
    return snapshot.to_dict() if snapshot.exists else None


def create_room(host_id, host_name, language, account=None, attempts=5):
    """Store a new room under an unused code. create() fails if the code is taken."""
    import multiplayer
    from google.api_core.exceptions import AlreadyExists

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
