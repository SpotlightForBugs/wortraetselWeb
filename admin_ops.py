"""Admin-only helpers. Privilege is a Firestore `admin` flag on the user doc."""

from __future__ import annotations

import os
import time

from firebase_admin import auth

import firebaseDB
import multiplayer


def bootstrap_emails():
    raw = os.environ.get("ADMIN_EMAILS") or ""
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def is_admin_email(email):
    if not email:
        return False
    if email.lower() in bootstrap_emails():
        return True
    return bool(firebaseDB.is_admin(email))


def ensure_bootstrap_admin(email):
    """Promote matching ADMIN_EMAILS accounts so the first admin does not need a manual edit."""
    if not email or email.lower() not in bootstrap_emails():
        return False
    if firebaseDB.is_admin(email):
        return False
    firebaseDB.set_admin(email, True)
    return True


def list_users(query="", limit=40):
    needle = (query or "").strip().lower()
    rows = []
    for user in firebaseDB.getUsers():
        email = (user.get("email") or "").lower()
        name = (user.get("username") or "").lower()
        if needle and needle not in email and needle not in name:
            continue
        rows.append(
            {
                "email": user.get("email") or "",
                "username": user.get("username")
                or (email.split("@")[0] if email else ""),
                "score": int(user.get("score") or 0),
                "admin": bool(user.get("admin")),
                "banned": bool(user.get("banned")),
            }
        )
    rows.sort(key=lambda row: (-row["score"], row["username"].lower()))
    return rows[: max(1, min(int(limit or 40), 100))]


def set_score(email, score):
    try:
        value = int(score)
    except (TypeError, ValueError):
        return False, "admin_bad_score"
    if value < 0:
        return False, "admin_bad_score"
    if not firebaseDB.setScore(email, value, overwrite=True):
        return False, "admin_user_missing"
    return True, value


def rename_user(email, username):
    username = (username or "").strip()
    if not 2 <= len(username) <= 20:
        return False, "bad_name"
    try:
        auth.update_user(auth.get_user_by_email(email).uid, display_name=username)
    except auth.UserNotFoundError:
        return False, "admin_user_missing"
    if not firebaseDB.set_username(email, username):
        return False, "admin_user_missing"
    return True, username


def set_banned(email, banned):
    try:
        user = auth.get_user_by_email(email)
    except auth.UserNotFoundError:
        return False, "admin_user_missing"
    auth.update_user(user.uid, disabled=bool(banned))
    if not firebaseDB.set_banned(email, bool(banned)):
        return False, "admin_user_missing"
    return True, bool(banned)


def delete_user(email, actor_email):
    if email == actor_email:
        return False, "admin_self"
    try:
        auth.delete_user(auth.get_user_by_email(email).uid)
    except auth.UserNotFoundError:
        pass
    firebaseDB.delete_user_doc(email)
    return True, None


def set_admin_flag(email, admin, actor_email):
    if email == actor_email and not admin:
        return False, "admin_self"
    if not firebaseDB.set_admin(email, bool(admin)):
        return False, "admin_user_missing"
    return True, bool(admin)


def list_rooms():
    rooms = []
    for snapshot in firebaseDB.getDB().collection("rooms").stream():
        room = snapshot.to_dict() or {}
        rooms.append(
            {
                "code": snapshot.id,
                "state": room.get("state"),
                "language": room.get("language"),
                "host": room.get("host"),
                "players": [
                    {
                        "id": p.get("id"),
                        "name": p.get("name"),
                        "score": p.get("score", 0),
                    }
                    for p in room.get("players") or []
                ],
                "word": room.get("word") or "",
                "updated_at": float(room.get("updated_at") or 0),
            }
        )
    rooms.sort(key=lambda row: -row["updated_at"])
    return rooms


def close_room(code):
    code = multiplayer.normalize_code(code)
    if not multiplayer.valid_code(code):
        return False, "mp_room_missing"
    room = firebaseDB.get_room(code)
    if not room:
        return False, "mp_room_missing"
    firebaseDB.delete_room(code)
    return True, code


def get_announcement():
    return firebaseDB.get_site_config().get("announcement") or ""


def set_announcement(message, actor_email):
    text = (message or "").strip()
    if len(text) > 280:
        return False, "admin_announcement_long"
    firebaseDB.set_site_config(
        {
            "announcement": text,
            "announcement_by": actor_email,
            "announcement_at": time.time(),
        }
    )
    return True, text
