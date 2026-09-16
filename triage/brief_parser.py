"""Parses a founder brief text file into sections, generically.

Convention expected: section headers are lines with no leading whitespace,
and bullets are lines starting with a tab, then a bullet character. This
makes no assumption about section names or wording, so a differently worded
brief that follows the same header/bullet convention parses correctly
without any code changes. The full raw text is also kept and handed to the
LLM verbatim, since section-splitting can lose phrasing nuance that matters
for classification.
"""
import re
from dataclasses import dataclass, field


@dataclass
class FounderBrief:
    raw_text: str
    sections: dict = field(default_factory=dict)  # header -> list[str] bullets

    def section(self, *keywords):
        """Bullets for the first section whose header contains all keywords (case-insensitive)."""
        for header, bullets in self.sections.items():
            h = header.lower()
            if all(k.lower() in h for k in keywords):
                return bullets
        return []


_BULLET_CHARS = ("•", "-", "*")


def parse_founder_brief(path: str) -> FounderBrief:
    with open(path, encoding="utf-8") as f:
        text = f.read()

    sections: dict[str, list[str]] = {}
    current_header = None
    for line in text.splitlines():
        if not line.strip():
            continue
        stripped = line.lstrip()
        is_bullet = line.startswith(("\t", "  ")) or stripped[:1] in _BULLET_CHARS
        if is_bullet and current_header is not None:
            bullet = re.sub(r"^[\t\-\*•\s]+", "", line).strip()
            if bullet:
                sections[current_header].append(bullet)
            continue
        current_header = stripped
        sections.setdefault(current_header, [])

    return FounderBrief(raw_text=text, sections=sections)
