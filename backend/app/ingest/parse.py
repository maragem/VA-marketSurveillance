"""Split an act's (X)HTML into articles.

EUR-Lex/CELLAR HTML renditions vary across decades of acts, so parsing works
on the extracted plain text: articles start at lines matching "Article N"
(optionally followed by a title line). This is deliberately tolerant — the
output is a human-reviewed proposal, not a directly trusted corpus.
"""
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

_SKIP_TAGS = {"script", "style", "head"}


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._skip_depth = 0
        self.lines: list[str] = []
        self._buffer: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        elif tag in {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "table"}:
            self._flush()

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
        elif tag in {"p", "div", "tr", "li", "h1", "h2", "h3", "h4"}:
            self._flush()

    def handle_data(self, data):
        if not self._skip_depth:
            self._buffer.append(data)

    def _flush(self):
        text = " ".join("".join(self._buffer).split())
        if text:
            self.lines.append(text)
        self._buffer = []

    def close(self):
        self._flush()
        super().close()


@dataclass
class Article:
    number: str
    title: str = ""
    paragraphs: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(self.paragraphs)


_ARTICLE_LINE = re.compile(r"^Article\s+(\d+[a-z]?)\s*$", re.IGNORECASE)
# End of the enacting terms: annexes or final signatures.
_TERMINATOR = re.compile(r"^(ANNEX\b|Done at\b)", re.IGNORECASE)


def html_to_lines(html: str) -> list[str]:
    extractor = _TextExtractor()
    extractor.feed(html)
    extractor.close()
    return extractor.lines


def split_articles(html: str) -> list[Article]:
    lines = html_to_lines(html)
    articles: list[Article] = []
    current: Article | None = None
    seen: set[str] = set()

    for line in lines:
        if _TERMINATOR.match(line) and current:
            break
        m = _ARTICLE_LINE.match(line)
        if m:
            number = m.group(1).lower()
            # Tables of contents repeat "Article N" lines; keep first occurrence
            # of each number in document order and start collecting only when
            # the body follows (a repeated number means we were in the ToC).
            if number in seen and articles:
                # restart collection at the real body occurrence
                existing = next(a for a in articles if a.number == number)
                existing.paragraphs = []
                existing.title = ""
                current = existing
                continue
            seen.add(number)
            current = Article(number=number)
            articles.append(current)
            continue
        if current is None:
            continue
        if not current.title and not current.paragraphs and len(line) < 150 and not line[0:1].isdigit():
            current.title = line
        else:
            current.paragraphs.append(line)

    return [a for a in articles if a.paragraphs or a.title]
