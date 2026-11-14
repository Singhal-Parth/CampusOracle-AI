"""Rank numbered sections of the bundled sample policies using SQLite FTS5."""

import re
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass
from pathlib import Path

KNOWLEDGE_BASE = Path(__file__).resolve().parent / "knowledge_base"
SECTION_HEADER = re.compile(r"^\s*\d+\.\s+(.+)$")
STOP_WORDS = frozenset("""
    a an and are about as at be by can could do does for from how i in is it me
    my of on or our please should tell than that the their this to was were
    what when where which who will with would you your college campus
    policies policy rules rule guidelines guideline
""".split())


@dataclass(frozen=True)
class Passage:
    document: str
    section: str
    start_line: int
    end_line: int
    excerpt: str

    def to_source(self, number: int) -> dict:
        return {"number": number, **asdict(self)}


def read_sections(directory: Path) -> list[Passage]:
    passages = []
    for path in sorted(directory.glob("*.txt")):
        lines = path.read_text(encoding="utf-8").splitlines()
        headings = [
            (index, match.group(1).strip())
            for index, line in enumerate(lines)
            if (match := SECTION_HEADER.fullmatch(line))
        ]
        ends = [index for index, _ in headings[1:]] + [len(lines)]
        for (start, title), end in zip(headings, ends):
            while not lines[end - 1].strip():
                end -= 1
            passages.append(Passage(path.name, title, start + 1, end, "\n".join(lines[start:end])))
    return passages


def search(query: str, directory: Path | None = None) -> list[Passage]:
    """Return at most three passages, breaking rank ties by file and section order."""
    words = re.findall(r"[^\W_]+", query.casefold())
    terms = list(dict.fromkeys(word for word in words if word not in STOP_WORDS))[:24]
    if not terms:
        return []
    passages = read_sections(KNOWLEDGE_BASE if directory is None else directory)
    if not passages:
        return []

    # Quote tokenizer output as FTS terms so user text can't introduce operators.
    match_query = " OR ".join(f'"{term}"' for term in terms)
    with closing(sqlite3.connect(":memory:")) as index:
        index.execute(
            "CREATE VIRTUAL TABLE sections USING fts5(title, body, tokenize='porter unicode61')"
        )
        index.executemany(
            "INSERT INTO sections(rowid, title, body) VALUES (?, ?, ?)",
            (
                (i, passage.section, passage.excerpt.split("\n", 1)[-1])
                for i, passage in enumerate(passages, start=1)
            ),
        )
        ranked = index.execute(
            "SELECT rowid FROM sections WHERE sections MATCH ? "
            "ORDER BY bm25(sections, 5.0, 1.0), rowid LIMIT 3",
            (match_query,),
        )
        return [passages[row_id - 1] for (row_id,) in ranked]
