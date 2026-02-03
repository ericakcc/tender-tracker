"""Official government Open Data XML source for historical tender data."""

from datetime import date, datetime
from pathlib import Path

import httpx
from loguru import logger
from lxml import etree

from tender_tracker.models import Tender
from tender_tracker.sources.base import TenderSource

OPENDATA_BASE_URL = "https://web.pcc.gov.tw/tps/tp/OpenData/showList"


class OpenDataSource(TenderSource):
    """Client for the official government Open Data XML feed."""

    def __init__(self, *, timeout: float = 60.0) -> None:
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": "TenderTracker/0.1"},
        )

    @property
    def name(self) -> str:
        return "opendata"

    async def fetch_by_date(self, target_date: date) -> list[Tender]:
        """Fetch tenders from official Open Data XML.

        Note: Official data has ~2 month delay. This fetches the latest
        available batch data, not real-time by-date data.

        Args:
            target_date: Target date (used for logging; actual data may differ).

        Returns:
            List of parsed tenders.
        """
        logger.info("Fetching from official Open Data XML")

        try:
            response = await self._client.get(OPENDATA_BASE_URL)
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error("Failed to fetch Open Data: {}", e)
            return []

        return self._parse_xml(response.content)

    async def search(self, keyword: str) -> list[Tender]:
        """Search is not supported for Open Data XML source.

        Args:
            keyword: Ignored.

        Returns:
            Empty list (search not supported for batch XML source).
        """
        logger.warning("Open Data XML source does not support keyword search")
        return []

    async def fetch_xml_file(self, file_path: Path) -> list[Tender]:
        """Parse a locally downloaded XML file.

        Args:
            file_path: Path to a downloaded Open Data XML file.

        Returns:
            List of parsed tenders.
        """
        if not file_path.exists():
            logger.error("XML file not found: {}", file_path)
            return []

        content = file_path.read_bytes()
        return self._parse_xml(content)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    def _parse_xml(self, content: bytes) -> list[Tender]:
        """Parse XML content into tender records.

        Args:
            content: Raw XML bytes.

        Returns:
            List of parsed tenders.
        """
        try:
            root = etree.fromstring(content)  # noqa: S320
        except etree.XMLSyntaxError as e:
            logger.error("Failed to parse XML: {}", e)
            return []

        tenders: list[Tender] = []

        # Try common XML structures from PCC Open Data
        for record in root.iter():
            if record.tag in ("record", "row", "data"):
                tender = self._parse_xml_record(record)
                if tender:
                    tenders.append(tender)

        # If no records found with known tags, try all children of root
        if not tenders:
            for child in root:
                tender = self._parse_xml_record(child)
                if tender:
                    tenders.append(tender)

        logger.info("Parsed {} tenders from XML", len(tenders))
        return tenders

    def _parse_xml_record(self, record: etree._Element) -> Tender | None:
        """Parse a single XML record element.

        Args:
            record: An XML element representing a tender.

        Returns:
            Parsed Tender or None.
        """
        try:

            def _text(tag: str) -> str:
                el = record.find(tag)
                return el.text.strip() if el is not None and el.text else ""

            tender_id = _text("tender_id") or _text("tenderId") or _text("pkAtmMain") or _text("id")
            title = _text("name") or _text("tenderName") or _text("title")

            if not tender_id or not title:
                return None

            budget_str = _text("budget") or _text("price") or _text("budgetAmount")
            budget = None
            if budget_str:
                try:
                    budget = float(budget_str.replace(",", ""))
                except ValueError:
                    pass

            deadline = _parse_date(_text("endDate") or _text("deadline"))

            return Tender(
                tender_id=tender_id,
                title=title,
                org_name=_text("unit") or _text("orgName") or _text("org_name"),
                procurement_type=_text("type") or _text("procurementType"),
                tender_method=_text("method") or _text("tenderMethod"),
                budget_amount=budget,
                deadline=deadline,
                url=_text("url") or "",
                category=_text("category") or "",
                source="opendata",
            )
        except Exception as e:
            logger.debug("Failed to parse XML record: {}", e)
            return None


def _parse_date(value: str) -> datetime | None:
    """Attempt to parse a date string."""
    if not value:
        return None
    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None
