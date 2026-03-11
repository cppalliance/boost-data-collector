"""
Fetcher for WG21 Papers.
Scrapes the WG21 papers index and specific mailing tables.
"""

import re
import urllib.parse
from typing import Optional

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

import logging

logger = logging.getLogger(__name__)

BASE_URL = "https://www.open-std.org/jtc1/sc22/wg21/docs/papers"

_MAILING_ANCHOR_RE = re.compile(r"^mailing\d{4}-\d{2}$")


def _find_table_in_section(anchor) -> Optional[Tag]:
    """
    Find the first <table> that belongs to the current mailing section.
    Stops at the next mailing anchor (id/name matching mailingYYYY-MM) so we
    do not attribute another mailing's table to this section.
    """
    if not anchor:
        return None
    anchor_id = anchor.get("id") or anchor.get("name") or ""
    if not _MAILING_ANCHOR_RE.match(anchor_id):
        return None
    for elem in anchor.next_elements:
        if not hasattr(elem, "name"):  # NavigableString, etc.
            continue
        if elem is anchor:
            continue
        if elem.name == "table":
            return elem
        if not hasattr(elem, "get"):  # e.g. NavigableString
            continue
        next_id = elem.get("id") or elem.get("name") or ""
        if next_id and _MAILING_ANCHOR_RE.match(next_id) and next_id != anchor_id:
            return None  # next section start; no table in this section
    return None


def fetch_all_mailings() -> list[dict]:
    """
    Fetch the main index and extract all mailings.
    Returns a list of dicts:
      - mailing_date (e.g. '2025-02')
      - title (e.g. '2025-02 pre-Hagenberg mailing')
      - year (e.g. '2025')
    List is in the order found on the page (usually newest first).
    """
    logger.info("Fetching WG21 main index: %s/", BASE_URL)
    try:
        response = requests.get(f"{BASE_URL}/", timeout=30)
        response.raise_for_status()
    except requests.RequestException:
        logger.exception("Failed to fetch WG21 index.")
        return []

    # The mailings are listed in a markdown-like syntax or links
    # Typically: <a href="2025/#mailing2025-02">2025-02 pre-Hagenberg mailing</a>
    # Let's parse with BeautifulSoup
    soup = BeautifulSoup(response.text, "html.parser")
    mailings = []

    # We look for links pointing to year/#mailingYYYY-MM
    pattern = re.compile(r"^(\d{4})/#mailing(\d{4}-\d{2})$")

    for a in soup.find_all("a", href=True):
        href = a["href"]
        match = pattern.search(href)
        if match:
            year, mailing_date = match.groups()
            title = a.text.strip()
            mailings.append(
                {"mailing_date": mailing_date, "title": title, "year": year}
            )

    return mailings


def fetch_papers_for_mailing(year: str, mailing_date: str) -> list[dict]:
    """
    Fetch the papers for a specific mailing from the year page.
    Returns a list of paper dicts.
    """
    url = f"{BASE_URL}/{year}/"
    logger.info("Fetching mailing %s from %s", mailing_date, url)
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
    except requests.RequestException:
        logger.exception("Failed to fetch year page %s.", year)
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    anchor_id = f"mailing{mailing_date}"
    anchor = soup.find(id=anchor_id) or soup.find(attrs={"name": anchor_id})
    if not anchor:
        logger.warning("Anchor %s not found on %s", anchor_id, url)
        return []

    table = _find_table_in_section(anchor)
    if not table:
        logger.warning("No table found after anchor %s", anchor_id)
        return []

    paper_urls = []
    paper_pattern = re.compile(r"((?:p\d+r\d+|n\d+|sd-\d+))\.([a-z]+)", re.IGNORECASE)

    for row in table.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if not cells or any(cell.get("colspan") for cell in cells):
            continue

        # Usually: Number, Title, Author, Date, Subgroup
        if len(cells) >= 1:
            first_cell = cells[0]
            for link in first_cell.find_all("a", href=True):
                href = link.get("href", "")
                match = paper_pattern.search(href)
                if match:
                    paper_url = urllib.parse.urljoin(url, href)
                    parsed = urllib.parse.urlparse(paper_url)
                    base = urllib.parse.urlparse(BASE_URL)
                    if (
                        parsed.scheme not in ("https", "http")
                        or parsed.netloc != base.netloc
                    ):
                        logger.warning("Skipping off-origin paper URL %s", paper_url)
                        continue

                    paper_id = match.group(1).lower()
                    file_ext = match.group(2).lower()
                    filename = match.group(0).lower()

                    title = ""
                    if len(cells) > 1:
                        title = cells[1].text.strip()

                    authors = []
                    if len(cells) > 2:
                        authors_raw = cells[2].text.strip()
                        # Split by comma or 'and' if multiple
                        if authors_raw:
                            authors = [
                                a.strip()
                                for a in re.split(r",| and ", authors_raw)
                                if a.strip()
                            ]

                    document_date = None
                    if len(cells) > 3:
                        date_str = cells[3].text.strip()
                        if date_str:
                            document_date = date_str  # Will be parsed/saved in pipeline

                    subgroup = ""
                    if len(cells) > 4:
                        subgroup = cells[4].text.strip()

                    paper_urls.append(
                        {
                            "url": paper_url,
                            "filename": filename,
                            "type": file_ext,
                            "paper_id": paper_id,
                            "title": title,
                            "authors": authors,
                            "document_date": document_date,
                            "subgroup": subgroup,
                        }
                    )
                    break  # Only take the first paper link in the cell

    # Remove exact duplicates (same filename)
    seen = set()
    unique_papers = []
    for p in paper_urls:
        if p["filename"] not in seen:
            seen.add(p["filename"])
            unique_papers.append(p)

    return unique_papers
