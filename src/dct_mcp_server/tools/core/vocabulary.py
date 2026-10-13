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


def _word_set_pattern(words: frozenset) -> re.Pattern | None:
    """
    One whole-word, case-insensitive pattern matching any of *words*.

    Whole-word on both sides: "profil" must not match "profile", and
    "mask" must not match "masks" unless "masks" is listed too. A space in a
    phrase also matches a hyphen, so "self service" covers "self-service".
    """
    if not words:
        return None
    alternatives = sorted(
        (r"[\s-]+".join(re.escape(part) for part in w.split()) for w in words),
        key=len,
        reverse=True,
    )
    return re.compile(rf"(?<![\w-])(?:{'|'.join(alternatives)})(?![\w-])", re.I)


@lru_cache(maxsize=1)
def _compiled_rules() -> tuple[tuple[re.Pattern, dict], ...]:
    """Compile each term rule into a whole-word, case-insensitive pattern."""
    compiled = []
    for rule in load_vocabulary_rules():
        rule = dict(rule)
        rule["_only_if"] = _word_set_pattern(rule["only_if_text_mentions"])
        rule["_skip_if"] = _word_set_pattern(rule.get("skip_if_text_mentions", ()))
        compiled.append(
            (re.compile(rf"\b{re.escape(rule['internal'])}\b", re.IGNORECASE), rule)
        )
    return tuple(compiled)


# Substrings that are machine identifiers rather than prose, and so must never
# be rewritten. Translating inside them produces a URL that does not exist
# ("/dct/v3/timelines/tf-1") or a resource ID that cannot be looked up
# ("delphix-postgres-connector"):
#   - URLs
#   - anything containing a "/" (API paths, POSIX file paths, "group/version")
#   - anything containing a "\\" (Windows paths: C:\\delphix\\toolkit\\bin)
#   - hyphen-, dot- or @-joined compounds (slugs, IDs, package names,
#     name@version: tf-1, delphix-postgres-plugin, com.delphix.toolkit,
#     toolkit@1.0.0)
#   - {placeholders} and `code spans`
_PROTECTED_RE = re.compile(
    r"https?://\S+"
    r"|`[^`\n]*`"
    r"|[\w.{}:~%$-]*/[\w.{}:~%$/-]*"
    r"|[\w.{}:~%$-]*\\[\w.{}:~%$\\-]*"
    r"|\w+(?:[-.@]\w+)+"
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


def _rule_applies(text: str, rule: dict) -> bool:
    """
    True when the text-level conditions of *rule* hold for *text*.

    ``only_if_text_mentions`` is positive evidence: without one of its words
    in the text the line does not apply at all. ``skip_if_text_mentions``
    vetoes the line when the text carries contrary evidence.
    """
    only_if, skip_if = rule.get("_only_if"), rule.get("_skip_if")
    if only_if is not None and not only_if.search(text):
        return False
    if skip_if is not None and skip_if.search(text):
        return False
    return True


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

# "a"/"an" ending the text just before a substituted term, so the article can
# be corrected when the substitution changes the following sound
# ("an AppData plugin" -> "a connector").
_TRAILING_ARTICLE_RE = re.compile(r"\b(a|an)(\s+)$", re.IGNORECASE)


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


def _fix_trailing_article(preceding: str, replacement: str) -> str:
    """
    Correct an "a"/"an" that ends *preceding* to agree with *replacement*.

    Only the article directly before a substituted term is touched: text the
    translation did not change is never rewritten, so upstream prose such as
    "a user" or "a unique ID" keeps its own (correct) article.
    """
    article = _TRAILING_ARTICLE_RE.search(preceding)
    if not article:
        return preceding
    correct = "an" if replacement[:1].lower() in "aeiou" else "a"
    if article.group(1)[:1].isupper():
        correct = correct.capitalize()
    return preceding[: article.start()] + correct + article.group(2)


def _merge_left_overlap(preceding: str, replacement: str) -> str:
    """
    Drop words ending *preceding* that the replacement already starts with.

    "VDB containers" must become "VDB Groups", not "VDB VDB Groups"; and a
    term written twice in two vocabularies ("VDB Group container") must not
    become "VDB Group VDB Group".
    """
    words = replacement.split()
    for k in range(len(words), 0, -1):
        tail = re.search(
            r"(?<![\w-])" + r"\s+".join(re.escape(w) for w in words[:k]) + r"\s+$",
            preceding,
            re.IGNORECASE,
        )
        if tail:
            return preceding[: tail.start()]
    return preceding


def _right_overlap(following: str, replacement: str) -> int:
    """
    Number of trailing replacement words that *following* already starts with.

    "container VDB Group" must become "VDB Group", not "VDB Group VDB Group".
    """
    words = replacement.split()
    for k in range(len(words), 0, -1):
        if re.match(
            r"\s+" + r"\s+".join(re.escape(w) for w in words[-k:]) + r"(?![\w-])",
            following,
            re.IGNORECASE,
        ):
            return k
    return 0


def to_canonical(text: str | None) -> str | None:
    """
    Rewrite internal Delphix terminology in *text* into canonical terms.

    Only prose is rewritten. URLs, paths, hyphen/dot/@-joined identifiers and
    {placeholders} are left byte-for-byte intact. Words with an everyday or
    ambiguous meaning ("container", "inventory", "Delphix engine") are only
    translated when the text carries positive evidence for the retired Delphix
    meaning -- see the guard directives in ``config/mappings/vocabulary.txt``.

    Args:
        text: Arbitrary upstream text, or None.

    Returns:
        The translated text, or *text* unchanged when there is nothing to
        translate. None in, None out.
    """
    if not text:
        return text
    return _translate(text)


# Pure function of the text: the compiled rules are fixed for the life of the
# process (_compiled_rules is cached the same way). OpenAPI summaries are
# re-translated on every discovery call, so memoising them is a cheap win;
# the bound keeps one-off error messages from growing it without limit.
@lru_cache(maxsize=8192)
def _translate(text: str) -> str:
    result = text
    settled: set[str] = set()

    for pattern, rule in _compiled_rules():
        internal = rule["internal"].lower()
        if internal in settled:
            # An earlier line for the same term already applied.
            continue
        if not pattern.search(result):
            # Cheap pre-check: most text carries none of the terms.
            continue
        # Text-level evidence is judged on the original, untranslated text so
        # an earlier substitution cannot manufacture or erase a signal.
        if not _rule_applies(text, rule):
            continue
        settled.add(internal)

        # Recomputed per rule: offsets move as earlier rules substitute.
        spans = _protected_spans(result)
        pieces, cursor = [], 0
        for match in pattern.finditer(result):
            if match.start() < cursor:
                continue
            if _inside(match.start(), match.end(), spans) or _guard_blocks(
                result, match, rule
            ):
                continue
            preceding = _merge_left_overlap(
                result[cursor : match.start()], rule["canonical"]
            )
            replacement = _match_case(
                match.group(0), rule["canonical"], result[:cursor] + preceding
            )
            end = match.end()
            overlap = _right_overlap(result[end:], replacement)
            if overlap == len(replacement.split()):
                # The following words already spell the whole term: drop the
                # match (and its trailing space) and keep that copy.
                following = result[end:].lstrip()
                pieces.append(_fix_trailing_article(preceding, following))
                cursor = len(result) - len(following)
                continue
            if overlap:
                replacement = " ".join(replacement.split()[:-overlap])
            pieces.append(_fix_trailing_article(preceding, replacement))
            pieces.append(replacement)
            cursor = end
        if pieces:
            pieces.append(result[cursor:])
            result = "".join(pieces)

    return result


def differs(original: str | None, translated: str | None) -> bool:
    """True when translation actually changed something worth surfacing."""
    return bool(translated) and translated != original
