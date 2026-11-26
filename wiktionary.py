"""Short glosses for the reveal screen. Missing entries stay silent.

English uses en.wiktionary REST, then en.wiktionary wikitext. Every other
hangman language uses that language's own Wiktionary first, then a local
dictionary when one is available:

  de → DWDS, es → RAE (rae-api), pt-br → Priberam,
  ro → Dexonline HTML synthesis (vxern/dexonline-scraper shape), tr → TDK

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
# HTML synthesis tab (same page vxern/dexonline-scraper scrapes), not /json.
_DEXONLINE = "https://dexonline.ro/definitie/{term}"
_TDK = "https://sozluk.gov.tr/gts?ara={term}"
_RAE = "https://rae-api.com/api/words/{term}"
_PRIBERAM = "https://dicionario.priberam.org/{term}"

_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")
_REF = re.compile(r"<ref\b[^>]*>.*?</ref>|<ref\b[^|]*/\s*>", re.S | re.I)
_BOLD = re.compile(r"'{2,}")
_WIKI_LINK = re.compile(r"\[\[(?:[^|\]]+\|)?([^\]]+)\]\]")
_WIKI_TEMPLATE = re.compile(r"\{\{[^{}]*\}\}")
_HTML_SUB = re.compile(r"<sub\b[^>]*>(.*?)</sub>", re.S | re.I)
_HTML_SUP = re.compile(r"<sup\b[^>]*>(.*?)</sup>", re.S | re.I)
# Digits/signs commonly used in chemical formulas and exponents.
_SUB_CHARS = str.maketrans("0123456789+-()aehklmnpst", "₀₁₂₃₄₅₆₇₈₉₊₋₍₎ₐₑₕₖₗₘₙₚₛₜ")
_SUP_CHARS = str.maketrans("0123456789+-()ni", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁽⁾ⁿⁱ")
_DE_SENSE = re.compile(r"^:\[(\d+)\]\s*(.+)$")
_DE_BEDEUTUNGEN = re.compile(r"\{\{Bedeutungen\}\}\s*(.*?)(?=\n\{\{[^\n]+\}|\Z)", re.S)
_ES_SENSE = re.compile(r"^;(\d+)\s*(?:\{\{[^{}]*\}\})?\s*:\s*(.+)$")
_DWDS_DEF = re.compile(r'class="dwdswb-definition"[^>]*>(.*?)</span>', re.S | re.I)
# Dexonline HTML synthesis rows (cheerio selectors from vxern/dexonline-scraper).
_DEX_MEANING_ROW = re.compile(
    r'<div class="meaning-row">(.*?)</div>\s*'
    r'(?=<div class="meaning-relations"|</div>)',
    re.S,
)
_DEX_TREE_DEF = re.compile(r'class="[^"]*tree-def[^"]*"[^>]*>(.*?)</span>', re.S | re.I)
_DEX_ROW_SOURCES = re.compile(
    r'class="[^"]*meaning-sources[^"]*"[^>]*>(.*?)</span>', re.S | re.I
)
# Literary examples usually end with AUTHOR, PAGE (CARAGIALE, O. III 92).
_DEX_EXAMPLE = re.compile(
    r"\b[A-ZĂÂÎȘŢ]{2,}(?:\s+[A-ZĂÂÎȘŢ]\.?)*,\s*" r"(?:[A-Z][A-Z0-9.\s]*)?\d+"
)
# Composition / bare cognate rows live beside real senses in the tree.
_DEX_ETYM_ROW = re.compile(r"(?:^\S+\s*\+\s*\S+$)|(^[A-Za-zÀ-ÿĂÂÎȘȚăâîșț''\-.]{2,40}$)")
# Mirror of vxern/dexonline-scraper copyrightedDictionaries (non-exhaustive).
_DEX_COPYRIGHTED = frozenset(
    {
        "MDA",
        "MDA2",
        "MDN '00",
        "MDN '08",
        "DOOM 2",
        "DOOM 3",
        "DLR",
        "DLRLC",
        "DEXI",
        "NODEX",
        "Scriban",
        "Sinonime",
        "Antonime",
        "Argou",
        "DER",
        "DA",
        "DN",
    }
)

# Display names cached with the gloss and shown as a "from …" badge.
_SOURCE_WIKTIONARY = "Wiktionary"
_SOURCE_LOCAL = {
    "de": "DWDS",
    "ro": "Dexonline",
    "tr": "TDK",
    "es": "RAE",
    "pt-br": "Priberam",
}
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


def _script_plain(text, table):
    """Map digits/signs in a sub/sup fragment; leave unknown chars as-is."""
    inner = _TAG.sub("", html.unescape(text or ""))
    return inner.translate(table)


def _html_scripts(text):
    """Turn <sub>/<sup> into Unicode, then drop any leftover HTML tags.

    Empty/None input is returned unchanged so callers can sanitize in place.
    """
    if not text:
        return text
    text = _HTML_SUB.sub(lambda m: _script_plain(m.group(1), _SUB_CHARS), text)
    text = _HTML_SUP.sub(lambda m: _script_plain(m.group(1), _SUP_CHARS), text)
    return _plain(text)


def _gloss_entry(definition, source, source_url):
    """Build the public ``{definition, source, source_url}`` payload."""
    return {
        "definition": _html_scripts(definition),
        "source": source or _SOURCE_WIKTIONARY,
        "source_url": source_url,
    }


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
    # de.wiktionary uses raw HTML for formulas (C<sub>2</sub>H<sub>2</sub>).
    # The reveal UI sets textContent, so tags must become Unicode here.
    return _html_scripts(text).strip(" :;.,")


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


def _ro_stem_forms(shown):
    """Likely dictionary lemmas for articulated/plural Romanian hangman words."""
    text = (shown or "").casefold()
    stems = []
    if len(text) < 5:
        return stems

    def add(form):
        if form and form != text and len(form) >= 3 and form not in stems:
            stems.append(form)

    if text.endswith(("ului", "ilor")):
        add(text[:-4])
    elif text.endswith("elor") and len(text) > 6:
        add(text[:-4])
        add(text[:-4] + "e")
    elif text.endswith("ile") and len(text) > 5:
        add(text[:-3])
        add(text[:-2])
    elif text.endswith("lor") and len(text) > 5:
        add(text[:-3])
    elif text.endswith("lui") and len(text) > 5:
        add(text[:-3])
    elif text.endswith("ul") and len(text) > 4:
        add(text[:-2])
    elif text.endswith("le") and len(text) > 5:
        add(text[:-2])
    elif text.endswith("ia") and len(text) > 4:
        # baciluria (def.) → bacilurie
        add(text[:-2] + "ie")
        add(text[:-1])
    elif text.endswith("ii") and len(text) > 4:
        add(text[:-1])
    elif text.endswith("i") and len(text) > 4:
        # ostatici → ostatic
        add(text[:-1])
    if text.endswith("a") and len(text) > 4:
        # agroterasa → agroterasă / agroterase
        add(text[:-1] + "ă")
        add(text[:-1] + "e")
        add(text[:-1])
    return stems


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
    if language == "ro":
        for stem in _ro_stem_forms(shown):
            for candidate in _titles(stem, language):
                if candidate not in base:
                    base.append(candidate)
    if not host:
        return base
    key = _ascii_fold(shown)
    found = []
    search_seeds = list(_search_seeds(shown, language))
    if language == "ro":
        for stem in _ro_stem_forms(shown):
            if stem not in search_seeds:
                search_seeds.append(stem)
    for seed in search_seeds:
        seed_key = _ascii_fold(seed)
        for title in _search_titles(host, seed):
            # Accept fold-match to the hangman word or to a stemmed lemma.
            if not (
                _title_fits_language(title, language, key)
                or _title_fits_language(title, language, seed_key)
            ):
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


def _dex_row_sources(chunk):
    """Source labels attached to one Dexonline meaning-row."""
    match = _DEX_ROW_SOURCES.search(chunk or "")
    if not match:
        return []
    raw = _plain(match.group(1))
    return [part.strip() for part in re.split(r"[,;/]", raw) if part.strip()]


def _dex_row_text(chunk):
    match = _DEX_TREE_DEF.search(chunk or "")
    if not match:
        return None
    return _SPACE.sub(" ", _plain(match.group(1))).strip(" .;")


def _dex_is_example(text):
    return bool(_DEX_EXAMPLE.search(text or ""))


def _dex_is_etymology(text):
    return bool(_DEX_ETYM_ROW.match((text or "").strip().rstrip(".")))


def _dex_sources_ok(sources, allow_copyrighted):
    if not sources:
        return True
    if allow_copyrighted:
        return True
    return any(source not in _DEX_COPYRIGHTED for source in sources)


def _dexonline_gloss(term):
    """First usable Dexonline definition from the HTML synthesis tab.

    Matches the approach in vxern/dexonline-scraper: scrape
    ``div.meaning-row`` / ``span.tree-def``, skip literary examples and
    etymology crumbs, and prefer non-copyrighted dictionary sources.
    """
    page = _request_text(_DEXONLINE.format(term=urllib.parse.quote(term)))
    if not page:
        return None
    rows = _DEX_MEANING_ROW.findall(page)
    if not rows:
        # Fallback: any tree-def span if markup shifted.
        rows = [
            f'<span class="tree-def html">{chunk}</span>'
            for chunk in _DEX_TREE_DEF.findall(page)
        ]
    for allow_copyrighted in (False, True):
        for chunk in rows:
            text = _dex_row_text(chunk)
            if not text or _dex_is_example(text) or _dex_is_etymology(text):
                continue
            sources = _dex_row_sources(chunk)
            if not _dex_sources_ok(sources, allow_copyrighted):
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
    """Return ``(gloss, source, page)`` from native Wiktionary then a local dictionary."""
    shown = game.display_word(language, word) or word
    candidates = _native_candidates(word, language)
    for term in candidates:
        gloss = _native_wiktionary_gloss(language, term)
        # Reject circular stubs even when the page title differs (maîson → Maison).
        if gloss and _usable(gloss, shown) and _usable(gloss, term):
            return gloss, _SOURCE_WIKTIONARY, term
    local_name = _SOURCE_LOCAL.get(language)
    for term in candidates:
        gloss = _local_gloss(language, term)
        if gloss and _usable(gloss, shown):
            return gloss, local_name or _SOURCE_WIKTIONARY, term
    return None, None, None


def _en_rest_gloss(word):
    """Return ``(gloss, page_title)`` from en.wiktionary REST, or ``(None, None)``."""
    shown = game.display_word("en", word) or word
    for term in _titles(shown, "en"):
        payload = _fetch_en(term)
        if not payload:
            continue
        gloss = _pick(payload, "en", word=term)
        if gloss:
            return gloss, term
    return None, None


def _source_url(source, language, page):
    """Public dictionary page for the gloss attribution chip."""
    page = (page or "").strip()
    if not page or not source:
        return None
    quoted = urllib.parse.quote(page)
    if source == _SOURCE_WIKTIONARY:
        host = _NATIVE_HOST.get(language) or "en"
        title = page.replace(" ", "_")
        return "https://{host}.wiktionary.org/wiki/{term}".format(
            host=host,
            term=urllib.parse.quote(title, safe=""),
        )
    if source == "DWDS":
        return _DWDS.format(term=quoted)
    if source == "Dexonline":
        return _DEXONLINE.format(term=quoted)
    if source == "TDK":
        return "https://sozluk.gov.tr/?ara={term}".format(term=quoted)
    if source == "RAE":
        return "https://dle.rae.es/{term}".format(term=quoted)
    if source == "Priberam":
        return _PRIBERAM.format(term=quoted)
    return None


def _lookup(word, language):
    """Return ``(gloss, source, page)`` or ``(None, None, None)``."""
    if language not in _LANG_KEY:
        return None, None, None
    if language == "en":
        gloss, page = _en_rest_gloss(word)
        if gloss:
            return gloss, _SOURCE_WIKTIONARY, page
        return _native_lookup(word, "en")
    # Never fall back to English Wiktionary for other languages.
    return _native_lookup(word, language)


def _cached_gloss_entry(cached, language, shown):
    """Turn a Firestore word_glosses row into a public entry, or None."""
    text = cached.get("definition")
    if not text:
        return None
    source = cached.get("source") or _SOURCE_WIKTIONARY
    url = cached.get("source_url") or _source_url(source, language, shown)
    # Re-sanitize so older cache rows with raw <sub>/<sup> still display.
    return _gloss_entry(text, source, url)


def define_entry(word, language):
    """Return ``{definition, source, source_url}`` or None for a miss / empty gloss.

    Firestore caches hits and misses (with source + url) under word_glosses.
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
        return _cached_gloss_entry(cached, language, shown)
    gloss, source, page = _lookup(shown, language)
    gloss = _html_scripts(gloss)
    source = source or (_SOURCE_WIKTIONARY if gloss else None)
    url = _source_url(source, language, page or shown) if gloss else None
    try:
        firebaseDB.set_word_gloss(language, shown, gloss, source=source, source_url=url)
    except Exception:
        pass
    if not gloss:
        return None
    return _gloss_entry(gloss, source, url)


def define(word, language):
    """Return one short gloss for this hangman language, or None."""
    entry = define_entry(word, language)
    return entry["definition"] if entry else None


def warm(word, language):
    """Fill the gloss cache without returning anything to the client.

    Safe to run on a background thread after the first guess of a round.
    """
    try:
        define_entry(word, language)
    except Exception:
        pass
