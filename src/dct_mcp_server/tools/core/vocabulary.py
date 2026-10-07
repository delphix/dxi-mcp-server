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

from dct_mcp_server.config.loader import load_vocabulary_map
from dct_mcp_server.core.logging import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def _compiled_terms() -> tuple[tuple[re.Pattern, str], ...]:
    """Compile the term map into whole-word, case-insensitive patterns."""
    return tuple(
        (re.compile(rf"\b{re.escape(internal)}\b", re.IGNORECASE), canonical)
        for internal, canonical in load_vocabulary_map()
    )


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

    Args:
        text: Arbitrary upstream text, or None.

    Returns:
        The translated text, or *text* unchanged when there is nothing to
        translate. None in, None out.
    """
    if not text:
        return text

    result = text
    for pattern, canonical in _compiled_terms():
        result = pattern.sub(
            lambda m, c=canonical: _match_case(m.group(0), c, m.string[: m.start()]),
            result,
        )
    return _fix_articles(result)


def differs(original: str | None, translated: str | None) -> bool:
    """True when translation actually changed something worth surfacing."""
    return bool(translated) and translated != original
