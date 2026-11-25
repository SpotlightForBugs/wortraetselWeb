"""Short glosses for the reveal screen. Missing entries stay silent.

English uses en.wiktionary REST, then en.wiktionary wikitext. Every other
hangman language uses that language's own Wiktionary first, then a local
dictionary when one is available:

  de → DWDS, es → RAE (rae-api), pt-br → Priberam, ro → Dexonline, tr → TDK

en.wiktionary is never used for non-English rounds so glosses stay
in-language. Accent-folded word lists are bridged via MediaWiki search
(casa → casă). Weak surname/given-name glosses and REDIRECT stubs are skipped.

Lookups are cached in Firestore (including negative misses). The first
guess of a round can warm the cache server-side via warm() without sending
the gloss to the client.
"""

import html
import json
import re
import unicodedata
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
_SEARCH = (
    "https://{host}.wiktionary.org/w/api.php"
    "?action=query&list=search&srsearch={term}&srnamespace=0&srlimit=8&format=json"
)
_OPENSEARCH = (
    "https://{host}.wiktionary.org/w/api.php"
    "?action=opensearch&search={term}&limit=8&redirects=resolve&format=json"
)
_DWDS = "https://www.dwds.de/wb/{term}"
_DEXONLINE = "https://dexonline.ro/definitie/{term}/json"
_TDK = "https://sozluk.gov.tr/gts?ara={term}"
_RAE = "https://rae-api.com/api/words/{term}"
_PRIBERAM = "https://dicionario.priberam.org/{term}"

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
_DEX_MARK = re.compile(r"[@$#]([^@$#]*)[@$#]")
_DEX_BRACKET = re.compile(r"\[[^\]]*\]")
# MDA2 marks senses as @1@ / @1-3@ / @1.@ before the gloss text.
_DEX_MARKED_SENSE = re.compile(
    r"@(\d+(?:\s*[-–]\s*\d+)?)(?:\.)?@\s*(.+?)(?=\s*@\d+(?:\s*[-–]\s*\d+)?(?:\.)?@|\s*$)",
    re.S,
)
# Fallback after markers are stripped: "1." / "1-3" / "I. 1.".
_DEX_SENSE = re.compile(
    r"(?:^|\s)(?:[IVX]+\.\s+)?(\d+(?:\s*[-–]\s*\d+)?)\s*[.)]?\s+(.+)$"
)
_DEX_NEXT_SENSE = re.compile(r"\s+\d+(?:\s*[-–]\s*\d+)?\s*[.)]?(?=\s+\S)")
_DEX_CUT = re.compile(r"\s+(?:\*|◊|♦)\s+")
# DEX '09/'16 often has no sense number: "APLIC'ARE, aplicări, s.f. Acțiunea…"
_DEX_POS_HEAD = re.compile(
    r"^.*?\b(?:s\.\s*[fnm]\.?|sf|sm|sn|adj\.?|vb\.?|adv\.?|interj\.?|prep\.?|conj\.?)\s+",
    re.I | re.S,
)
_DEX_XREF = re.compile(r"\s+-\s*[Vv]\.\s+")
_DEX_META_LEFT = re.compile(r"\[At:|\bPl:|\bE:\s|[@#$]")
_DEX_HEADWORD_LEFT = re.compile(r"^[A-ZĂÂÎȘŢ]{2,}['’`]?[A-ZĂÂÎȘŢ]*\b")
_META_DESC = re.compile(r'<meta\s+name="description"\s+content="([^"]+)"', re.I)
_PRIBERAM_GLOSS = re.compile(r":\s*(.+?)\s*(?:—|-)\s*Dicion", re.S)
_RAE_PREFIX = re.compile(r"^\d+\.?[a-z]?\.?\s*(?:[fma]\.|[a-z]+\.)*\s*", re.I)
_WEAK_GLOSS = re.compile(
    r"^(?:a |an |eine? )?"
    r"(?:surname|given name|family name|male given name|female given name|"
    r"patronymic|matronymic|place name|nom de famille|prénom|"
    r"nachname|vorname|ehrenname)"
    r"(?:[,.].*)?$",
    re.I,
)
_REDIRECT = re.compile(r"^REDIRECT\b", re.I)
# Acute/grave stress marks alone (casa → casá) are not real lemma restorations.
_STRESS_MARKS = set("áéíóúàèìòùÁÉÍÓÚÀÈÌÒÙ")

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

# Non-ASCII letters allowed on search hits for each hangman language.
# Blocks cross-wiki false friends (casa → caŝa, ev → év).
_DIACRITICS = {
    "de": set("äöüßÄÖÜ"),
    "es": set("áéíóúüñÁÉÍÓÚÜÑ"),
    "fr": set("àâäæçéèêëïîôœùûüÿÀÂÄÆÇÉÈÊËÏÎÔŒÙÛÜŸ"),
    "it": set("àèéìíîòóùúÀÈÉÌÍÎÒÓÙÚ"),
    "pt-br": set("áàâãéêíóôõúüçÁÀÂÃÉÊÍÓÔÕÚÜÇ"),
    "ro": set("ăâîșşțţĂÂÎȘŞȚŢ"),
    "tr": set("âçğıİîöşüûÂÇĞÎÖŞÜÛ"),
    "en": set("'"),
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
    if re.fullmatch(r"[fm]\s*(?:sing|pl)?", text, re.I):
        return False
    if _WEAK_GLOSS.match(text.strip().rstrip(".")):
        return False
    if _REDIRECT.match(text.strip()):
        return False
    return True


def _ascii_fold(text):
    text = unicodedata.normalize("NFD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.casefold()


def _title_fits_language(title, language, key):
    """True when title folds to the hangman word and only uses that language's letters."""
    if not title or " " in title.strip():
        return False
    if _ascii_fold(title) != key:
        return False
    allowed = _DIACRITICS.get(language) or set()
    for ch in title:
        if ord(ch) < 128:
            continue
        if ch not in allowed:
            return False
    return True


def _only_stress_marks(title, shown):
    """True for stress-only variants like casa → casá (not casă / enseñanza)."""
    if not title or title.casefold() == (shown or "").casefold():
        return False
    if _ascii_fold(title) != _ascii_fold(shown):
        return False
    extras = [ch for ch in title if ord(ch) >= 128]
    return bool(extras) and all(ch in _STRESS_MARKS for ch in extras)


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


def _search_seeds(word, language):
    """Extra search queries for accent-folded hangman spellings."""
    raw = (word or "").strip()
    if not raw:
        return []
    seeds = [raw]
    if language == "tr":
        # Hangman folds ö/ü to oe/ue; try the umlaut forms for search.
        unfolded = raw.replace("oe", "ö").replace("ue", "ü").replace("ae", "ä")
        if unfolded != raw:
            seeds.append(unfolded)
        stripped = raw.replace("oe", "o").replace("ue", "u").replace("ae", "a")
        if stripped != raw:
            seeds.append(stripped)
    elif language == "de":
        unfolded = (
            raw.replace("ae", "ä")
            .replace("oe", "ö")
            .replace("ue", "ü")
            .replace("ss", "ß")
        )
        if unfolded != raw:
            seeds.append(unfolded)
    return seeds


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


def _search_titles(host, term):
    """Titles from fulltext search plus opensearch prefix suggestions."""
    seen = []
    quoted = urllib.parse.quote(term)
    payload = _request_json(_SEARCH.format(host=host, term=quoted))
    hits = ((payload or {}).get("query") or {}).get("search") or []
    for hit in hits:
        title = hit.get("title") or ""
        if title and title not in seen:
            seen.append(title)
    suggestions = _request_json(_OPENSEARCH.format(host=host, term=quoted))
    if isinstance(suggestions, list) and len(suggestions) > 1:
        for title in suggestions[1] or []:
            if title and title not in seen:
                seen.append(title)
    return seen


def _native_candidates(word, language):
    """Page titles to try: accented search hits first, then casing variants.

    Accent-folded lists (ro casa, fr formalisee) often collide with a
    different ASCII lemma. Prefer fold-matched titles that restore marks
    (casă, formalisée) before the bare hangman spelling.
    """
    shown = game.display_word(language, word) or word
    host = _NATIVE_HOST.get(language)
    base = []
    for candidate in _titles(shown, language):
        if candidate not in base:
            base.append(candidate)
    if not host:
        return base
    key = _ascii_fold(shown)
    found = []
    for seed in _search_seeds(shown, language):
        for title in _search_titles(host, seed):
            if not _title_fits_language(title, language, key):
                continue
            if title not in found:
                found.append(title)
    # Prefer titles that *add* diacritics (casa → casă), never ones that
    # strip them (casă → casa), so the verb "casa" cannot beat the noun.
    shown_marks = sum(1 for ch in shown if ord(ch) >= 128)
    preferred = [
        title
        for title in found
        if title.casefold() != shown.casefold()
        and not _only_stress_marks(title, shown)
        and sum(1 for ch in title if ord(ch) >= 128) > shown_marks
    ]
    # Bare hangman spelling before stress-only lookalikes (casá).
    ordered = []
    for title in preferred + base + found:
        if _only_stress_marks(title, shown):
            continue
        if title not in ordered:
            ordered.append(title)
    return ordered


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


def _dexonline_gloss(term):
    """First Dexonline sense for a Romanian lemma, or None.

    Dexonline ``internalRep`` mixes lemma, POS, bracketed attestation, and
    sense text with ``@``/``$``/``#`` markers. MDA2 often uses range heads
    like ``@1-3@`` instead of ``@1.@``, so a narrow ``1.`` match used to
    return the whole headword line (e.g. baciluria).
    """
    payload = _request_json(_DEXONLINE.format(term=urllib.parse.quote(term)))
    if not payload:
        return None
    for entry in payload.get("definitions") or []:
        rep = html.unescape(entry.get("internalRep") or "")
        if not rep:
            continue
        marked = _DEX_MARKED_SENSE.search(rep)
        if marked:
            text = marked.group(2)
        else:
            text = _DEX_BRACKET.sub("", rep)
            for _ in range(6):
                cleaned = _DEX_MARK.sub(r"\1", text)
                if cleaned == text:
                    break
                text = cleaned
            text = _SPACE.sub(" ", text).strip()
            match = _DEX_SENSE.search(text)
            if match:
                text = match.group(2)
            else:
                text = _DEX_POS_HEAD.sub("", text, count=1)
            text = _DEX_NEXT_SENSE.split(text, maxsplit=1)[0]
        # Nested @ $ # still sit inside the sense body (##a##, @$lemma$@).
        text = _DEX_BRACKET.sub("", text)
        for _ in range(6):
            cleaned = _DEX_MARK.sub(r"\1", text)
            if cleaned == text:
                break
            text = cleaned
        text = _DEX_CUT.split(text, maxsplit=1)[0]
        text = _DEX_XREF.split(text, maxsplit=1)[0]
        text = _SPACE.sub(" ", text).strip(" .;")
        if _DEX_META_LEFT.search(text) or _DEX_HEADWORD_LEFT.match(text):
            continue
        if _usable(text, term):
            return text
    return None


def _tdk_gloss(term):
    """First TDK (sozluk.gov.tr) sense for a Turkish lemma, or None."""
    payload = _request_json(_TDK.format(term=urllib.parse.quote(term)))
    if not payload or isinstance(payload, dict):
        return None
    for entry in payload:
        for sense in entry.get("anlamlarListe") or []:
            text = _SPACE.sub(" ", (sense.get("anlam") or "")).strip()
            # Skip cross-reference stubs like "► aile".
            if text.startswith("►") or text.startswith("→"):
                continue
            if _usable(text, term):
                return text
    return None


def _rae_gloss(term):
    """First RAE sense via rae-api.com, or None."""
    payload = _request_json(_RAE.format(term=urllib.parse.quote(term)))
    if not payload:
        return None
    data = payload.get("data") or {}
    for meaning in data.get("meanings") or []:
        for sense in meaning.get("senses") or []:
            text = (sense.get("description") or "").strip()
            if not text:
                text = _RAE_PREFIX.sub("", sense.get("raw") or "").strip()
                # Drop trailing example sentence when description was empty.
                if ". " in text:
                    text = text.split(". ", 1)[0].strip()
            if _usable(text, term):
                return text
    return None


def _priberam_gloss(term):
    """Priberam meta-description gloss for Portuguese, or None."""
    page = _request_text(_PRIBERAM.format(term=urllib.parse.quote(term)))
    if not page:
        return None
    match = _META_DESC.search(page)
    if not match:
        return None
    desc = html.unescape(match.group(1))
    gloss = _PRIBERAM_GLOSS.search(desc)
    text = gloss.group(1) if gloss else desc
    text = re.sub(r"^Significado de [^:]+:\s*", "", text, flags=re.I)
    text = text.split("—")[0].split(" - Dicion")[0]
    text = _SPACE.sub(" ", text).strip(" .…;")
    if _usable(text, term):
        return text
    return None


def _local_gloss(language, term):
    """Language-specific national dictionary fallback after Wiktionary."""
    if language == "de":
        return _dwds_gloss(term)
    if language == "ro":
        return _dexonline_gloss(term)
    if language == "tr":
        return _tdk_gloss(term)
    if language == "es":
        return _rae_gloss(term)
    if language == "pt-br":
        return _priberam_gloss(term)
    return None


def _native_lookup(word, language):
    shown = game.display_word(language, word) or word
    candidates = _native_candidates(word, language)
    for term in candidates:
        gloss = _native_wiktionary_gloss(language, term)
        # Reject circular stubs even when the page title differs (maîson → Maison).
        if gloss and _usable(gloss, shown) and _usable(gloss, term):
            return gloss
    for term in candidates:
        gloss = _local_gloss(language, term)
        if gloss and _usable(gloss, shown):
            return gloss
    return None


def _en_rest_gloss(word):
    shown = game.display_word("en", word) or word
    for term in _titles(shown, "en"):
        payload = _fetch_en(term)
        if not payload:
            continue
        gloss = _pick(payload, "en", word=term)
        if gloss:
            return gloss
    return None


def _lookup(word, language):
    if language not in _LANG_KEY:
        return None
    if language == "en":
        return _en_rest_gloss(word) or _native_lookup(word, "en")
    # Never fall back to English Wiktionary for other languages.
    return _native_lookup(word, language)


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
