from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass

HEADING_RE = re.compile(r"^(#{2,4})\s+(.+?)\s*$", re.MULTILINE)
MARKDOWN_NOISE_RE = re.compile(r"[`*_>\[\]()!#|~-]+")
WHITESPACE_RE = re.compile(r"\s+")


def slugify(value: str, *, fallback: str = "item") -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return value or fallback


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def markdown_to_plain_text(markdown: str) -> str:
    value = MARKDOWN_NOISE_RE.sub(" ", markdown or "")
    return WHITESPACE_RE.sub(" ", value).strip()


def word_count(text: str) -> int:
    return len(re.findall(r"\w+", text or ""))


def reading_minutes(words: int, words_per_minute: int = 220) -> int:
    if words <= 0:
        return 0
    return max(1, round(words / words_per_minute))


@dataclass(slots=True)
class ParsedSection:
    slug: str
    anchor: str
    title: str
    level: int
    order_index: int
    body_markdown: str
    body_plain_text: str
    body_hash: str
    word_count: int
    reading_time_minutes: int
    materialized_path: str
    parent_order_index: int | None = None


def parse_markdown_sections(markdown: str) -> list[ParsedSection]:
    matches = list(HEADING_RE.finditer(markdown or ""))
    if not matches:
        plain = markdown_to_plain_text(markdown)
        words = word_count(plain)
        return [
            ParsedSection(
                slug="overview",
                anchor="overview",
                title="Overview",
                level=1,
                order_index=0,
                body_markdown=markdown or "",
                body_plain_text=plain,
                body_hash=sha256_text(markdown or ""),
                word_count=words,
                reading_time_minutes=reading_minutes(words),
                materialized_path="0000",
            )
        ]

    sections: list[ParsedSection] = []
    counters_by_slug: dict[str, int] = {}
    stack: list[tuple[int, int, str]] = []

    for index, match in enumerate(matches):
        level = len(match.group(1))
        raw_title = match.group(2).strip().strip("#").strip()
        base_slug = slugify(raw_title, fallback=f"section-{index + 1}")
        count = counters_by_slug.get(base_slug, 0)
        counters_by_slug[base_slug] = count + 1
        slug = base_slug if count == 0 else f"{base_slug}-{count + 1}"
        anchor = slug

        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        body = markdown[start:end].strip()
        plain = markdown_to_plain_text(f"{raw_title}\n{body}")
        words = word_count(plain)

        while stack and stack[-1][0] >= level:
            stack.pop()
        parent_order_index = stack[-1][1] if stack else None
        path_parts = [part for _, _, part in stack] + [f"{index:04d}"]
        materialized_path = "/".join(path_parts)
        stack.append((level, index, f"{index:04d}"))

        sections.append(
            ParsedSection(
                slug=slug,
                anchor=anchor,
                title=raw_title,
                level=level,
                order_index=index,
                body_markdown=body,
                body_plain_text=plain,
                body_hash=sha256_text(f"{raw_title}\n{body}"),
                word_count=words,
                reading_time_minutes=reading_minutes(words),
                materialized_path=materialized_path,
                parent_order_index=parent_order_index,
            )
        )
    return sections
