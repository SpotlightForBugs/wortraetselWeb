"""Short glosses for the reveal screen. Missing entries stay silent.

Primary source is English Wiktionary REST (all hangman languages). German
falls back to de.wiktionary MediaWiki wikitext, then a DWDS page scrape.
Lookups are cached in Firestore (including negative misses). The first
guess of a round can warm the cache server-side via warm() without sending
the gloss to the client.
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
_EN_API = "https://en.wiktionary.org/api/rest_v1/page/definition/{term}"
_DE_PARSE = (
    "https://de.wiktionary.org/w/api.php"
    "?action=parse&page={term}&prop=wikitext&format=json"
)
_DWDS = "https://www.dwds.de/wb/{term}"
_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")
_WIKI_LINK = re.compile(r"\[\[(?:[^|\]]+\|)?([^\]]+)\]\]")
_WIKI_TEMPLATE = re.compile(r"\{\{[^{}]*\}\}")
_DE_SENSE = re.compile(r"^:\[(\d+)\]\s*(.+)$")
_DE_BEDEUTUNGEN = re.compile(
    r"\{\{Bedeutungen\}\}\s*(.*?)(?=\n\{\{[^\n]+\}|\Z)", re.S
)
_DWDS_DEF = re.compile(
    r'class="dwdswb-definition"[^>]*>(.*?)</span>', re.S | re.I
)

# Hangman language -> Wiktionary language code in the en.wiktionary payload.
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


def _wiki_plain(text):
    """Strip MediaWiki link/template markup down to readable gloss text."""
    text = _WIKI_LINK.sub(r"\1", text or "")
    # Nested templates are rare in short sense lines; peel a few times.
    for _ in range(3):
        cleaned = _WIKI_TEMPLATE.sub("", text)
        if cleaned == text:
            break
        text = cleaned
    return _SPACE.sub(" ", text).strip(" :;")


def _titles(word, language):
    """Candidate dictionary page titles for a hangman word.

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


def _request_json(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": _UA, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=4) as response:
            return json.load(response)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError):
        return None


def _request_text(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": _UA, "Accept": "text/html"},
    )
    try:
        with urllib.request.urlopen(request, timeout=4) as response:
            return response.read().decode("utf-8", "replace")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError):
        return None


def _fetch_en(term):
    return _request_json(_EN_API.format(term=urllib.parse.quote(term)))


def _de_wiktionary_gloss(term):
    """First sense from de.wiktionary Bedeutungen, or None."""
    payload = _request_json(_DE_PARSE.format(term=urllib.parse.quote(term)))
    if not payload or payload.get("error"):
        return None
    wikitext = (payload.get("parse") or {}).get("wikitext") or {}
    body = wikitext.get("*") or ""
    match = _DE_BEDEUTUNGEN.search(body)
    if not match:
        return None
    for line in match.group(1).splitlines():
        sense = _DE_SENSE.match(line.strip())
        if not sense:
            continue
        text = _wiki_plain(sense.group(2))
        if text:
            return text
    return None


def _dwds_gloss(term):
    """First DWDS definition span for a German lemma, or None."""
    page = _request_text(_DWDS.format(term=urllib.parse.quote(term)))
    if not page:
        return None
    for chunk in _DWDS_DEF.findall(page):
        text = _plain(chunk)
        if text:
            return text
    return None


def _german_fallback(word):
    shown = game.display_word("de", word) or word
    for term in _titles(shown, "de"):
        gloss = _de_wiktionary_gloss(term)
        if gloss:
            return gloss
    for term in _titles(shown, "de"):
        gloss = _dwds_gloss(term)
        if gloss:
            return gloss
    return None


def _lookup(word, language):
    lang_key = _LANG_KEY.get(language)
    if not lang_key:
        return None
    shown = game.display_word(language, word) or word
    for term in _titles(shown, language):
        payload = _fetch_en(term)
        if not payload:
            continue
        gloss = _pick(payload, lang_key)
        if gloss:
            return gloss
    if language == "de":
        return _german_fallback(word)
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
