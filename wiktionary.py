"""Short glosses from English Wiktionary. Missing entries stay silent.

Lookups are cached in Firestore (including negative misses) so repeat
reveals do not hammer the API. The first guess of a round can warm the
cache server-side via warm() without sending the gloss to the client.
"""

import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request

import firebaseDB
import game

_UA = "HangmanWordGame/1.0 (https://github.com/SpotlightForBugs/wortraetselWeb)"
_API = "https://en.wiktionary.org/api/rest_v1/page/definition/{term}"
_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")

# Hangman language -> Wiktionary language code in the REST payload.
_LANG_KEY = {
    "en": "en",
    "de": "de",
    "es": "es",
    "fr": "fr",
    "it": "it",
    "pt-br": "pt",
    "ro": "ro",
    "tr": "tr",
}


def _plain(text):
    text = html.unescape(_TAG.sub("", text or ""))
    return _SPACE.sub(" ", text).strip()


def _titles(word, language):
    """Candidate Wiktionary page titles for a hangman word.

    English stays lowercase so Proper-noun surname pages (Labrum) do not
    beat the common-noun entry (labrum). Other languages still try the
    titled form first (German nouns, etc.).
    """
    raw = (word or "").strip()
    if not raw:
        return []
    lower = raw.lower()
    seen = []
    if language == "en":
        candidates = (lower, raw)
    else:
        titled = lower[:1].upper() + lower[1:] if lower else ""
        candidates = (titled, lower, raw)
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.append(candidate)
    return seen


def _pick(payload, lang_key):
    blocks = payload.get(lang_key) or []
    for block in blocks:
        for entry in block.get("definitions") or []:
            text = _plain(entry.get("definition"))
            if text:
                return text
    return None


def _fetch(term):
    url = _API.format(term=urllib.parse.quote(term))
    request = urllib.request.Request(
        url,
        headers={"User-Agent": _UA, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=4) as response:
            return json.load(response)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError):
        return None


def _lookup(word, language):
    lang_key = _LANG_KEY.get(language)
    if not lang_key:
        return None
    shown = game.display_word(language, word) or word
    for term in _titles(shown, language):
        payload = _fetch(term)
        if not payload:
            continue
        gloss = _pick(payload, lang_key)
        if gloss:
            return gloss
    return None


def define(word, language):
    """Return one short gloss for this hangman language, or None.

    Firestore caches hits and misses under word_glosses.
    """
    language = game.coerce_language(language)
    shown = (game.display_word(language, word) or word or "").strip().lower()
    if not shown or language not in _LANG_KEY:
        return None
    try:
        cached = firebaseDB.get_word_gloss(language, shown)
    except Exception:
        cached = None
    if cached is not None:
        text = cached.get("definition")
        return text if text else None
    gloss = _lookup(shown, language)
    try:
        firebaseDB.set_word_gloss(language, shown, gloss)
    except Exception:
        pass
    return gloss


def warm(word, language):
    """Fill the gloss cache without returning anything to the client.

    Safe to run on a background thread after the first guess of a round.
    """
    try:
        define(word, language)
    except Exception:
        pass
