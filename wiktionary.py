"""Short glosses for the reveal screen. Missing entries stay silent.

English uses en.wiktionary REST first. Other hangman languages prefer that
language's own Wiktionary (MediaWiki wikitext), then en.wiktionary REST, and
German also tries a DWDS page scrape. Weak surname/given-name glosses are
skipped.

The wiktionaryparser PyPI package is not used: it scrapes printable en.wiki
HTML and currently returns empty definitions.

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
_PARSE = (
    "https://{host}.wiktionary.org/w/api.php"
    "?action=parse&page={term}&prop=wikitext&format=json"
)
_DWDS = "https://www.dwds.de/wb/{term}"

_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")
_REF = re.compile(r"<ref\b[^>]*>.*?</ref>|<ref\b[^|]*/\s*>", re.S | re.I)
_BOLD = re.compile(r"'{2,}")
_WIKI_LINK = re.compile(r"\[\[(?:[^|\]]+\|)?([^\]]+)\]\]")
_WIKI_TEMPLATE = re.compile(r"\{\{[^{}]*\}\}")
_DE_SENSE = re.compile(r"^:\[(\d+)\]\s*(.+)$")
_DE_BEDEUTUNGEN = re.compile(r"\{\{Bedeutungen\}\}\s*(.*?)(?=\n\{\{[^\n]+\}|\Z)", re.S)
_ES_SENSE = re.compile(r"^;(\d+)\s*(?:\{\{[^{}]*\}\})?\s*:\s*(.+)$")
_DWDS_DEF = re.compile(r'class="dwdswb-definition"[^>]*>(.*?)</span>', re.S | re.I)
_WEAK_GLOSS = re.compile(
    r"^(?:a |an |eine? )?"
    r"(?:surname|given name|family name|male given name|female given name|"
    r"patronymic|matronymic|place name|nom de famille|prénom|"
    r"nachname|vorname|ehrenname)"
    r"(?:[,.].*)?$",
    re.I,
)

# Hangman language -> en.wiktionary REST language key / native wiki host.
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
_NATIVE_HOST = {
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


# Single-arg templates whose argument is the visible word (es.wiktionary plm).
_KEEP_TEMPLATE_ARG = re.compile(
    r"\{\{(?:plm|diminutivo|aumentativo)\|([^{}|]+)\}\}",
    re.I,
)


def _wiki_plain(text):
    """Strip MediaWiki link/template markup down to readable gloss text."""
    text = _REF.sub("", text or "")
    text = _BOLD.sub("", text)
    text = _WIKI_LINK.sub(r"\1", text)
    text = _KEEP_TEMPLATE_ARG.sub(r"\1", text)
    # Nested templates are rare in short sense lines; peel a few times.
    for _ in range(4):
        cleaned = _WIKI_TEMPLATE.sub("", text)
        if cleaned == text:
            break
        text = cleaned
    return _SPACE.sub(" ", text).strip(" :;.,")


def _usable(text, word=None):
    if not text or len(text) < 3:
        return False
    if word and text.casefold() == (word or "").casefold():
        return False
    # Morphology crumbs left after template stripping (Italian gender lines).
    if re.fullmatch(r"[fm]\s*(?:sing|pl)?", text, re.I):
        return False
    if _WEAK_GLOSS.match(text.strip().rstrip(".")):
        return False
    return True


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


def _pick(payload, lang_key, word=None):
    blocks = payload.get(lang_key) or []
    for block in blocks:
        for entry in block.get("definitions") or []:
            text = _plain(entry.get("definition"))
            if _usable(text, word):
                return text
    return None


def _request_json(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": _UA, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=2.5) as response:
            return json.load(response)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError):
        return None


def _request_text(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": _UA, "Accept": "text/html"},
    )
    try:
        with urllib.request.urlopen(request, timeout=2.5) as response:
            return response.read().decode("utf-8", "replace")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError):
        return None


def _fetch_en(term):
    return _request_json(_EN_API.format(term=urllib.parse.quote(term)))


def _fetch_wikitext(host, term):
    url = _PARSE.format(host=host, term=urllib.parse.quote(term))
    payload = _request_json(url)
    if not payload or payload.get("error"):
        return None
    wikitext = (payload.get("parse") or {}).get("wikitext") or {}
    body = wikitext.get("*") or ""
    return body or None


def _extract_de(body, word=None):
    match = _DE_BEDEUTUNGEN.search(body or "")
    if not match:
        return None
    for line in match.group(1).splitlines():
        sense = _DE_SENSE.match(line.strip())
        if not sense:
            continue
        text = _wiki_plain(sense.group(2))
        if _usable(text, word):
            return text
    return None


def _extract_es(body, word=None):
    for line in (body or "").splitlines():
        sense = _ES_SENSE.match(line.strip())
        if not sense:
            continue
        text = _wiki_plain(sense.group(2))
        if _usable(text, word):
            return text
    return None


def _extract_hash(body, word=None):
    """First `#` definition line (fr/en/pt/ro/tr, and it when usable)."""
    lines = (body or "").splitlines()
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("#"):
            continue
        if stripped.startswith(("#*", "#:", "#;", "##")):
            continue
        text = _wiki_plain(stripped[1:])
        if _usable(text, word):
            return text
    # Italian often puts the gloss on `#*` after a morphology `#` line.
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("#*") or stripped.startswith("#**"):
            continue
        text = _wiki_plain(stripped[2:])
        if _usable(text, word) and len(text) >= 12:
            return text
    return None


def _extract_native(language, body, word=None):
    if language == "de":
        return _extract_de(body, word)
    if language == "es":
        return _extract_es(body, word)
    return _extract_hash(body, word)


def _native_wiktionary_gloss(language, term):
    host = _NATIVE_HOST.get(language)
    if not host:
        return None
    body = _fetch_wikitext(host, term)
    if not body:
        return None
    return _extract_native(language, body, word=term)


def _dwds_gloss(term):
    """First DWDS definition span for a German lemma, or None."""
    page = _request_text(_DWDS.format(term=urllib.parse.quote(term)))
    if not page:
        return None
    for chunk in _DWDS_DEF.findall(page):
        text = _plain(chunk)
        if _usable(text, term):
            return text
    return None


def _fallback(word, language):
    shown = game.display_word(language, word) or word
    for term in _titles(shown, language):
        gloss = _native_wiktionary_gloss(language, term)
        if gloss:
            return gloss
    if language == "de":
        for term in _titles(shown, "de"):
            gloss = _dwds_gloss(term)
            if gloss:
                return gloss
    return None


def _en_rest_gloss(word, language):
    lang_key = _LANG_KEY.get(language)
    if not lang_key:
        return None
    shown = game.display_word(language, word) or word
    for term in _titles(shown, language):
        payload = _fetch_en(term)
        if not payload:
            continue
        gloss = _pick(payload, lang_key, word=term)
        if gloss:
            return gloss
    return None


def _lookup(word, language):
    if language not in _LANG_KEY:
        return None
    # Native wiki first for non-English so players get in-language senses
    # (en.wiktionary often only has English one-word glosses like "house").
    if language == "en":
        return _en_rest_gloss(word, language) or _fallback(word, language)
    return _fallback(word, language) or _en_rest_gloss(word, language)


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
