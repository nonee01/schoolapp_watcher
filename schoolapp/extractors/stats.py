from __future__ import annotations

from bs4 import BeautifulSoup

from ..models import MarkStatistics
from ._tables import normalize_cell


def parse_mark_statistics(html: str, element: str = "", eval_kind: str = "",
                          au: str = "", note: str = "") -> MarkStatistics | None:
    """The /notes-stat/elemevalsat popup: div.stat with a <p> title and a th/td stat table."""
    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one("div.stat") or soup
    title_node = scope.find("p")
    title = normalize_cell(title_node.get_text(" ", strip=True)) if title_node else ""

    rows: list[list[str]] = []
    table = scope.find("table")
    if table:
        for tr in table.find_all("tr"):
            cols = tr.find_all(["th", "td"])
            parsed = [normalize_cell(c.get_text(" ", strip=True)) for c in cols]
            if parsed and any(parsed):
                rows.append(parsed)

    if not rows and not title:
        return None
    return MarkStatistics(element=element, eval_kind=eval_kind, au=au, note=note,
                          title=title, rows=rows, raw={"title": title})
