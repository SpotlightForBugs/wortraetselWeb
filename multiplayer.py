"""Shared-room hangman. Pure room logic; storage lives in firebaseDB."""

import secrets

import game

MAX_PLAYERS = 8
CODE_LENGTH = 5
# No 0/O or 1/I so a code read aloud is unambiguous.
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def make_room_code(length=CODE_LENGTH):
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(length))


def normalize_code(code):
    return (code or "").strip().upper()


def valid_code(code):
    code = normalize_code(code)
    return len(code) == CODE_LENGTH and all(ch in _CODE_ALPHABET for ch in code)


def _player(player_id, name, account=None):
    return {"id": player_id, "name": name, "account": account, "hits": 0}


def new_room(code, host_id, host_name, language, account=None):
    return {
        "room_code": code,
        "host": host_id,
        "players": [_player(host_id, host_name, account)],
        "word": "",
        "language": game.coerce_language(language),
        "letters": [],
        "wrong_guesses": 0,
        "turn": 0,
        "state": "waiting",
        "result": None,
    }


def is_member(room, player_id):
    return any(p["id"] == player_id for p in (room or {}).get("players") or [])


def add_player(room, player_id, name, account=None):
    """Return (room, error). Joining twice is a no-op."""
    if is_member(room, player_id):
        return room, None
    if room.get("state") == "playing":
        return room, "mp_room_started"
    if len(room.get("players") or []) >= MAX_PLAYERS:
        return room, "mp_room_full"
    room = dict(room)
    room["players"] = list(room.get("players") or []) + [
        _player(player_id, name, account)
    ]
    return room, None


def start_room(room, player_id, word=None):
    """The host starts (or restarts) a round with a fresh word."""
    if player_id != room.get("host"):
        return room, "mp_host_only"
    if room.get("state") == "playing":
        return room, "mp_room_started"
    room = dict(
        room,
        word=word or game.getRandomWord(room.get("language")),
        letters=[],
        wrong_guesses=0,
        turn=0,
        state="playing",
        result=None,
    )
    room["players"] = [dict(p, hits=0) for p in room.get("players") or []]
    return room, None


def current_player(room):
    players = room.get("players") or []
    if not players:
        return None
    return players[int(room.get("turn") or 0) % len(players)]["id"]


def room_winner(room):
    """The player with the most revealed letters in a solved word, or None on a tie or loss."""
    status = game.round_status(
        room.get("word"), room.get("letters") or [], room.get("wrong_guesses") or 0
    )
    if status != "won":
        return None
    players = room.get("players") or []
    if not players:
        return None
    best = max(p.get("hits", 0) for p in players)
    leaders = [p for p in players if p.get("hits", 0) == best]
    return leaders[0]["id"] if len(leaders) == 1 else None


def guess(room, player_id, letter):
    """Apply one guess. A hit keeps the turn, a miss passes it on."""
    if room.get("state") != "playing":
        return room, "mp_not_playing"
    if current_player(room) != player_id:
        return room, "mp_not_your_turn"
    letter = (letter or "").lower()
    if len(letter) != 1 or not letter.isalpha() or letter in room.get("letters", []):
        return room, "mp_bad_letter"
    word = room["word"]
    letters, wrong, status = game.apply_guess(
        word, room.get("letters") or [], room.get("wrong_guesses") or 0, letter
    )
    players = [dict(p) for p in room["players"]]
    index = int(room.get("turn") or 0) % len(players)
    room = dict(room, letters=letters, wrong_guesses=wrong, players=players)
    if letter in word:
        players[index]["hits"] = players[index].get("hits", 0) + word.count(letter)
    else:
        room["turn"] = (index + 1) % len(players)
    if status != "playing":
        room["state"] = "finished"
        room["result"] = {
            "status": status,
            "word": word,
            "points": game.calculate_points(wrong, word, letters, status == "won"),
            "winner": room_winner(room),
        }
    return room, None


def public_state(room):
    """What every player may see. The word stays hidden until the round ends."""
    word = room.get("word") or ""
    letters = room.get("letters") or []
    wrong = room.get("wrong_guesses") or 0
    status = game.round_status(word, letters, wrong) if word else "playing"
    finished = room.get("state") == "finished"
    return {
        "room_code": room.get("room_code"),
        "state": room.get("state"),
        "language": room.get("language"),
        "host": room.get("host"),
        "players": [
            {"id": p["id"], "name": p.get("name"), "hits": p.get("hits", 0)}
            for p in room.get("players") or []
        ],
        "turn": current_player(room) if room.get("state") == "playing" else None,
        "tiles": game.reveal(word, letters, status) if word else [],
        "letter_states": game.letter_states(letters, word),
        "wrong_guesses": wrong,
        "drawing": game.drawing_for(wrong, status if word else "playing"),
        "result": room.get("result") if finished else None,
    }


def remove_player(room, player_id):
    """Drop a player. The host role and the turn move on so the round never stalls."""
    players = room.get("players") or []
    index = next((i for i, p in enumerate(players) if p["id"] == player_id), None)
    if index is None:
        return room, None
    remaining = players[:index] + players[index + 1 :]
    room = dict(room, players=remaining)
    if not remaining:
        room["state"] = "waiting"
        room["turn"] = 0
        return room, None
    if room.get("host") == player_id:
        room["host"] = remaining[0]["id"]
    turn = int(room.get("turn") or 0) % len(players)
    if index < turn:
        turn -= 1
    room["turn"] = turn % len(remaining)
    return room, None
