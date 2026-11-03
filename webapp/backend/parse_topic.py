"""Topic-line parsing helpers shared by the frontend and backend.

Topic lines may use plain names or optional suffixes:

    <name> - 85%
    <name> - Close to 85%
    <name> Page 3
    <name> Page 3 - 85%
    <name> Page 3 - Close to 85%
    <name> Page 3 - Hardcore
    <name> Page 3 - keepCards
    <name> Page 3 - skipCards
    <name> Page 3 - noNewCards

parse_topic_line(name) -> dict with keys:
    term, area, page, closeness_pct, hardcore, keepCards, skipCards, noNewCards

The simple Markdown frontmatter parser in the Notes browser scans cards for
lines like:

    [Lecture 1] Normalisation
    Topic: Normalisation     Page 3     - 85%
    Topic: Transactions       Page 4     - Close to 90%

Some values are used for the course guide renderer, including course title,
course.card.page, and instructions for the user.
"""
import re
from typing import Dict, Any, Union


def parse_topic_line(name: str) -> Dict[str, Any]:
    """Parse a topic name with optional suffixes.

    Returns a dict:
        term: str
        page: int|None
        closeness: int|None  (percentage closeness to the target)
        hardcore: bool
        keepCards: bool
        skipCards: bool
        noNewCards: bool
    """
    if not isinstance(name, str) or not name.strip():
        return {"term": None, "page": None, "closeness": None, "hardcore": False,
                "keepCards": False, "skipCards": False, "noNewCards": False}

    s = name.strip()
    page: Union[int, None] = None
    closeness: Union[int, None] = None
    hardcore = False
    keepCards = False
    skipCards = False
    noNewCards = False

    m = re.search(r"Page\s*(?:\(?(\d+)\s*\)?)", s, flags=re.I)
    if m:
        page = int(m.group(1))
        s = s[:m.start()] + s[m.end():]

    m = re.search(r"-\s*([0-9]+)\s*%", s)
    if m:
        closeness = int(m.group(1))
        s = s[:m.start()] + s[m.end():]

    rest = s.strip()
    if re.search(r"-?\s*Close to\s*[0-9]+%", rest, flags=re.I):
        closeness = int(re.search(r"([0-9]+)\s*%", rest, flags=re.I).group(1)) if re.search(r"([0-9]+)\s*%", rest, flags=re.I) else closeness

    if "Hardcore" in rest or "hardcore" in rest:
        hardcore = True
    if "KeepCards" in rest or "keepCards" in rest:
        keepCards = True
    if "SkipCards" in rest or "skipCards" in rest:
        skipCards = True
    if "NoNewCards" in rest or "noNewCards" in rest:
        noNewCards = True

    return {"term": rest or name.strip(), "page": page, "closeness": closeness,
            "hardcore": hardcore, "keepCards": keepCards, "skipCards": skipCards,
            "noNewCards": noNewCards}


if __name__ == "__main__":
    for line in [
        "Normalisation - 85%",
        "Normalisation - Close to 85%",
        "Page 3 - 85%",
        "Page 3 - Close to 85%",
        "Transactions - Page 3 - 85% - Hardcore - keepCards",
        "Transactions - Page 3 - 85% - Hardcore - skipCards",
        "Transactions - Page 3 - 85% - Hardcore - noNewCards",
    ]:
        print(repr(line), "->", parse_topic_line(line))
