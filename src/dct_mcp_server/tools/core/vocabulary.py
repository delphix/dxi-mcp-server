"""
Vocabulary translation for upstream text (PPM-1129).

Raw DCT error bodies and OpenAPI summaries reach the model verbatim and carry
Delphix-internal terminology ("timeflow", "AppData", "toolkit"). This module
renders such text into the canonical customer-facing vocabulary.

The term map is data, not code: see ``config/mappings/vocabulary.txt``.

Translation is *additive* at every call site. The raw upstream text is always
preserved alongside the translation, so diagnostics are never lost and the
HTTP status can still be parsed back out of the original message.
"""

import re
from functools import lru_cache

from dct_mcp_server.config.loader import load_vocabulary_rules
from dct_mcp_server.core.logging import get_logger

logger = get_logger(__name__)
@lru_cache(maxsize=1)
def _compiled_rules() -> tuple[tuple[re.Pattern, dict], ...]:
    """Compile each term rule into a whole-word, case-insensitive pattern."""
    return tuple(
        (re.compile(rf"\b{re.escape(rule['internal'])}\b", re.IGNORECASE), rule)
        for rule in load_vocabulary_rules()
    )


# Substrings that are machine identifiers rather than prose, and so must never
# be rewritten. Translating inside them produces a URL that does not exist
# ("/dct/v3/timelines/tf-1") or a resource ID that cannot be looked up
# ("delphix-postgres-connector"):
#   - URLs
#   - anything containing a "/" (API paths, file paths, "group/version")
#   - hyphen- or dot-joined compounds (slugs, IDs, package names: tf-1,
#     delphix-postgres-plugin, com.delphix.toolkit)
#   - {placeholders}
_PROTECTED_RE = re.compile(
    r"https?://\S+"
    r"|[\w.{}:~%-]*/[\w.{}:~%/-]*"
    r"|\w+(?:[-.]\w+)+"
    r"|\{[^{}]*\}"
)

_PREV_WORD_RE = re.compile(r"(\w+)\s+$")
_NEXT_WORD_RE = re.compile(r"^\s+(\w+)")
_WORD_RE = re.compile(r"\w+")


def _protected_spans(text: str) -> list[tuple[int, int]]:
    return [m.span() for m in _PROTECTED_RE.finditer(text)]


def _inside(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    """
    True when the match [start, end) touches a protected span.

    A span lying wholly within the match does not count: that is a term whose
    own spelling is hyphenated ("Self-Service container"), not a match carved
    out of a larger identifier.
    """
    return any(
        s < end and start < e and not (start <= s and e <= end) for s, e in spans
    )


def _text_mentions(text_lower: str, words: frozenset) -> bool:
    """True when any of *words* (single words or phrases) occurs in the text."""
    return any(re.search(rf"\b{re.escape(w)}", text_lower) for w in words)


def _guard_blocks(text: str, match: re.Match, rule: dict) -> bool:
    """True when the words around *match* say this is a different meaning."""
    before = rule["skip_if_preceded_by"]
    after = rule["skip_if_followed_by"]
    if before:
        prev = _PREV_WORD_RE.search(text[: match.start()])
        if prev and prev.group(1).lower() in before:
            return True
    if after:
        nxt = _NEXT_WORD_RE.search(text[match.end() :])
        if nxt and nxt.group(1).lower() in after:
            return True
    return False




# A word boundary preceded by sentence-ending punctuation, or the very start
# of the text. Used to decide whether a replacement should be capitalised.
_SENTENCE_START_RE = re.compile(r"(?:^|[.!?]\s+|\n\s*)$")

# "a"/"an" immediately before a word, so the article can be corrected after a
# substitution changes the following sound ("an AppData" -> "a connector").
_ARTICLE_RE = re.compile(r"\b(a|an|A|An)(\s+)(\w)", re.IGNORECASE)


def _match_case(matched: str, replacement: str, preceding: str) -> str:
    """
    Cast *replacement* into the right case for where it appears.

    The canonical term carries its own authored capitalisation ("connector" is
    a common noun, "SQL Server" and "VDB Group" are proper), so that is the
    default. Only two contexts override it: an all-caps match (an error code
    shouting at us) and the start of a sentence.
    """
    if matched.isupper() and len(matched) > 1 and replacement.islower():
        return replacement.upper()
    if _SENTENCE_START_RE.search(preceding):
        return replacement[:1].upper() + replacement[1:]
    return replacement


def _fix_articles(text: str) -> str:
    """Correct a/an after substitution changed the following word."""

    def _sub(match: re.Match) -> str:
        article, gap, first = match.group(1), match.group(2), match.group(3)
        correct = "an" if first.lower() in "aeiou" else "a"
        if article[:1].isupper():
            correct = correct.capitalize()
        return f"{correct}{gap}{first}"

    return _ARTICLE_RE.sub(_sub, text)


def to_canonical(text: str | None) -> str | None:
    """
    Rewrite internal Delphix terminology in *text* into canonical terms.

    Only prose is rewritten. URLs, paths, hyphen/dot-joined identifiers and
    {placeholders} are left byte-for-byte intact, and a term whose neighbouring
    words show it means something else ("Docker container", "Oracle container
    database", "VDB inventory report") is skipped -- see the guard directives
    in ``config/mappings/vocabulary.txt``.

    Args:
        text: Arbitrary upstream text, or None.

    Returns:
        The translated text, or *text* unchanged when there is nothing to
        translate. None in, None out.
    """
    if not text:
        return text

    original_lower = text.lower()
    result = text
    settled: set[str] = set()

    for pattern, rule in _compiled_rules():
        internal = rule["internal"].lower()
        if internal in settled:
            # An earlier line for the same term already applied.
            continue
        required = rule["only_if_text_mentions"]
        if required and not _text_mentions(original_lower, required):
            continue
        settled.add(internal)

        # Recomputed per rule: offsets move as earlier rules substitute.
        spans = _protected_spans(result)
        pieces, cursor = [], 0
        for match in pattern.finditer(result):
            if _inside(match.start(), match.end(), spans) or _guard_blocks(
                result, match, rule
            ):
                continue
            pieces.append(result[cursor : match.start()])
            pieces.append(
                _match_case(match.group(0), rule["canonical"], result[: match.start()])
            )
            cursor = match.end()
        if pieces:
            pieces.append(result[cursor:])
            result = "".join(pieces)

    return _fix_articles(result)


def differs(original: str | None, translated: str | None) -> bool:
    """True when translation actually changed something worth surfacing."""
    return bool(translated) and translated != original
