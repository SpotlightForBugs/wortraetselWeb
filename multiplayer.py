"""Shared-room hangman. Pure room logic; storage lives in firebaseDB."""

import random
import re
import secrets
import time

import game

MAX_PLAYERS = 8
MIN_PLAYERS = 2
CODE_LENGTH = 5
# Seconds a player has for one guess before anyone in the room may skip them.
TURN_SECONDS = 30
# Consecutive timed-out turns before an idle player is removed from the room.
AFK_STRIKES = 2
# Rooms with no activity this long are deleted so abandoned lobbies do not pile up.
ROOM_TTL_SECONDS = 2 * 60 * 60
# No 0/O or 1/I so a code read aloud is unambiguous.
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def make_room_code(length=CODE_LENGTH):
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(length))


def normalize_code(code):
    return (code or "").strip().upper()


def valid_code(code):
    code = normalize_code(code)
    return len(code) == CODE_LENGTH and all(ch in _CODE_ALPHABET for ch in code)


def sanitize_name(name, fallback):
    """Keep a short display name guests can choose themselves."""
    cleaned = re.sub(r"\s+", " ", (name or "").strip())
    cleaned = "".join(ch for ch in cleaned if ch.isprintable())
    cleaned = cleaned[:20].strip()
    return cleaned or fallback


def _player(player_id, name, account=None):
    return {
        "id": player_id,
        "name": name,
        "account": account,
        "hits": 0,
        "misses": 0,
        "round": 0,
        "score": 0,
        "strikes": 0,
    }


def new_room(code, host_id, host_name, language, account=None, now=None):
    stamp = time.time() if now is None else now
    return {
        "room_code": code,
        "host": host_id,
        "players": [_player(host_id, host_name, account)],
        "word": "",
        "language": game.coerce_language(language),
        "letters": [],
        "wrong_guesses": 0,
        "turn": 0,
        "turn_started": 0,
        "state": "waiting",
        "result": None,
        "notice": None,
        "starter": 0,
        "updated_at": stamp,
    }


def touch(room, now=None):
    """Mark the room as recently used so cleanup keeps it."""
    return dict(room, updated_at=time.time() if now is None else now)


def is_stale(room, now=None):
    now = time.time() if now is None else now
    if not (room.get("players") or []):
        return True
    return now - float(room.get("updated_at") or 0) >= ROOM_TTL_SECONDS


def is_member(room, player_id):
    return any(p["id"] == player_id for p in (room or {}).get("players") or [])


def add_player(room, player_id, name, account=None, now=None):
    """Return (room, error). Joining twice is a no-op."""
    if is_member(room, player_id):
        return room, None
    if room.get("state") == "playing":
        return room, "mp_room_started"
    if len(room.get("players") or []) >= MAX_PLAYERS:
        return room, "mp_room_full"
    room = touch(dict(room), now)
    room["players"] = list(room.get("players") or []) + [
        _player(player_id, name, account)
    ]
    return room, None


def set_language(room, player_id, language, now=None):
    """The host picks the word language between rounds."""
    if player_id != room.get("host"):
        return room, "mp_host_only"
    if room.get("state") == "playing":
        return room, "mp_room_started"
    if not game.isValidLanguage(language):
        return room, "mp_bad_language"
    return touch(dict(room, language=language), now), None


def start_room(room, player_id, word=None, now=None, rng=None):
    """The host starts (or restarts) a round with a fresh word.

    The first turn rotates so the host does not always open. The very first
    round picks a random starter; later rounds pass the opening seat along.
    """
    if player_id != room.get("host"):
        return room, "mp_host_only"
    if room.get("state") == "playing":
        return room, "mp_room_started"
    players = room.get("players") or []
    if len(players) < MIN_PLAYERS:
        return room, "mp_need_players"
    stamp = time.time() if now is None else now
    picker = rng or random
    if room.get("state") == "finished":
        starter = (int(room.get("starter") or 0) + 1) % len(players)
    else:
        starter = picker.randrange(len(players))
    room = dict(
        room,
        word=word or game.getRandomWord(room.get("language")),
        letters=[],
        wrong_guesses=0,
        turn=starter,
        starter=starter,
        turn_started=stamp,
        state="playing",
        result=None,
        notice=None,
        last_guess=None,
        updated_at=stamp,
    )
    room["players"] = [dict(p, hits=0, misses=0, round=0, strikes=0) for p in players]
    return room, None


def current_player(room):
    players = room.get("players") or []
    if not players:
        return None
    return players[int(room.get("turn") or 0) % len(players)]["id"]


def room_winner(room):
    """Highest letter-score this round on a win; None on a tie or loss."""
    status = game.round_status(
        room.get("word"), room.get("letters") or [], room.get("wrong_guesses") or 0
    )
    if status != "won":
        return None
    players = room.get("players") or []
    if not players:
        return None
    best = max(p.get("round", 0) for p in players)
    leaders = [p for p in players if p.get("round", 0) == best]
    return leaders[0]["id"] if len(leaders) == 1 else None


def round_shares(players):
    """Each player's letter-score for this round (already applied to score)."""
    return {p["id"]: int(p.get("round") or 0) for p in players}


def _finish(room, status, now=None):
    word = room["word"]
    letters = room.get("letters") or []
    language = room.get("language")
    points = game.calculate_points(
        room.get("wrong_guesses") or 0, word, letters, status == "won", language
    )
    shares = round_shares(room["players"])
    room["state"] = "finished"
    room["result"] = {
        "status": status,
        "word": game.display_word(language, word),
        "points": points,
        "shares": shares,
        "winner": room_winner(room),
        "letter_values": game.letter_values(language),
    }
    return touch(room, now)


def guess(room, player_id, letter, now=None):
    """Apply one guess. A hit keeps the turn, a miss passes it on.

    Points land immediately from the language's letter table so both sides see
    why a guess paid what it did.
    """
    if room.get("state") != "playing":
        return room, "mp_not_playing"
    if current_player(room) != player_id:
        return room, "mp_not_your_turn"
    letter = (letter or "").lower()
    if len(letter) != 1 or not letter.isalpha() or letter in room.get("letters", []):
        return room, "mp_bad_letter"
    word = room["word"]
    language = room.get("language")
    delta = game.score_guess(language, word, letter)
    letters, wrong, status = game.apply_guess(
        word, room.get("letters") or [], room.get("wrong_guesses") or 0, letter
    )
    players = [dict(p) for p in room["players"]]
    index = int(room.get("turn") or 0) % len(players)
    players[index]["strikes"] = 0
    players[index]["round"] = players[index].get("round", 0) + delta
    players[index]["score"] = players[index].get("score", 0) + delta
    stamp = time.time() if now is None else now
    room = dict(
        room,
        letters=letters,
        wrong_guesses=wrong,
        players=players,
        notice=None,
        last_guess={
            "player": player_id,
            "letter": letter.upper(),
            "points": delta,
            "value": game.letter_value(language, letter),
        },
        turn_started=stamp,
        updated_at=stamp,
    )
    if letter in word:
        players[index]["hits"] = players[index].get("hits", 0) + word.count(letter)
    else:
        players[index]["misses"] = players[index].get("misses", 0) + 1
        room["turn"] = (index + 1) % len(players)
    if status != "playing":
        room = _finish(room, status, now=stamp)
    return room, None


def skip_turn(room, player_id, now=None):
    """Any player may skip someone whose time ran out; repeat offenders are removed."""
    now = time.time() if now is None else now
    if room.get("state") != "playing":
        return room, "mp_not_playing"
    if not is_member(room, player_id):
        return room, "mp_room_missing"
    if now - float(room.get("turn_started") or 0) < TURN_SECONDS:
        return room, "mp_too_early"
    players = [dict(p) for p in room["players"]]
    index = int(room.get("turn") or 0) % len(players)
    idle = players[index]
    idle["strikes"] = idle.get("strikes", 0) + 1
    room = dict(room, players=players, turn_started=now, updated_at=now)
    if idle["strikes"] >= AFK_STRIKES:
        room, _ = remove_player(room, idle["id"], now=now)
        room["notice"] = {"type": "removed", "name": idle["name"]}
        return room, None
    room["turn"] = (index + 1) % len(players)
    room["notice"] = {"type": "timeout", "name": idle["name"]}
    return room, None


def remove_player(room, player_id, now=None):
    """Drop a player. The host role and the turn move on so the round never stalls."""
    players = room.get("players") or []
    index = next((i for i, p in enumerate(players) if p["id"] == player_id), None)
    if index is None:
        return room, None
    remaining = players[:index] + players[index + 1 :]
    room = touch(dict(room, players=remaining), now)
    if not remaining:
        room["state"] = "waiting"
        room["turn"] = 0
        return room, None
    if room.get("host") == player_id:
        # Hosting needs an account, so hand it to a signed-in player when there is one.
        heirs = [p for p in remaining if p.get("account")] or remaining
        room["host"] = heirs[0]["id"]
    turn = int(room.get("turn") or 0) % len(players)
    if index < turn:
        turn -= 1
    room["turn"] = turn % len(remaining)
    if index == turn:
        room["turn_started"] = time.time() if now is None else now
    return room, None


def public_state(room, now=None):
    """What every player may see. The word stays hidden until the round ends."""
    word = room.get("word") or ""
    letters = room.get("letters") or []
    wrong = room.get("wrong_guesses") or 0
    status = game.round_status(word, letters, wrong) if word else "playing"
    playing = room.get("state") == "playing"
    finished = room.get("state") == "finished"
    return {
        "room_code": room.get("room_code"),
        "state": room.get("state"),
        "language": room.get("language"),
        "host": room.get("host"),
        "min_players": MIN_PLAYERS,
        "max_players": MAX_PLAYERS,
        "players": [
            {
                "id": p["id"],
                "name": p.get("name"),
                "hits": p.get("hits", 0),
                "score": p.get("score", 0),
                "signed_in": bool(p.get("account")),
            }
            for p in room.get("players") or []
        ],
        "turn": current_player(room) if playing else None,
        "turn_deadline": (
            float(room.get("turn_started") or 0) + TURN_SECONDS if playing else None
        ),
        "server_now": time.time() if now is None else now,
        "notice": room.get("notice"),
        "tiles": (
            game.reveal(word, letters, status, room.get("language")) if word else []
        ),
        "letter_states": game.letter_states(letters, word),
        "letter_values": game.letter_values(room.get("language")),
        "wrong_guesses": wrong,
        "drawing": game.drawing_for(wrong, status if word else "playing"),
        "last_guess": room.get("last_guess") if playing or finished else None,
        "result": room.get("result") if finished else None,
    }
