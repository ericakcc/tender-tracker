"""g0v PCC API client — backup data source."""

import asyncio
from datetime import date, datetime

import httpx
from loguru import logger

from tender_tracker.models import Tender
from tender_tracker.sources.base import TenderSource

BASE_URL = "https://pcc-api.openfun.app/api"
REQUEST_DELAY = 3.0  # seconds between requests (Cloudflare protected)


class G0vSource(TenderSource):
    """Client for the g0v PCC API (backup source)."""

    def __init__(self, *, timeout: float = 30.0) -> None:
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            timeout=timeout,
            headers={"User-Agent": "TenderTracker/0.1"},
        )

    @property
    def name(self) -> str:
        return "g0v"

    async def fetch_by_date(self, target_date: date) -> list[Tender]:
        """Fetch tenders by date from g0v API.

        Args:
            target_date: Date to fetch tenders for.

        Returns:
            List of parsed tenders.
        """
        date_str = target_date.strftime("%Y%m%d")
        logger.info("Fetching tenders for date {} from g0v", date_str)

        try:
            response = await self._client.get(f"/date/{date_str}")
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error("Failed to fetch from g0v: {}", e)
            return []

        data = response.json()
        if not isinstance(data, list):
            logger.warning("Unexpected response format from g0v")
            return []

        tenders = [self._parse_tender(item) for item in data if item]
        tenders = [t for t in tenders if t is not None]
        logger.info("Fetched {} tenders from g0v for {}", len(tenders), date_str)
        return tenders

    async def search(self, keyword: str) -> list[Tender]:
        """Search tenders by keyword via g0v API.

        Args:
            keyword: Search term.

        Returns:
            List of matching tenders.
        """
        logger.info("Searching g0v for keyword: {}", keyword)
        await asyncio.sleep(REQUEST_DELAY)

        try:
            response = await self._client.get(f"/search/{keyword}")
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error("Failed to search g0v: {}", e)
            return []

        data = response.json()
        if not isinstance(data, list):
            return []

        tenders = [self._parse_tender(item) for item in data if item]
        tenders = [t for t in tenders if t is not None]
        logger.info("Found {} tenders for keyword '{}' from g0v", len(tenders), keyword)
        return tenders

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    def _parse_tender(self, item: dict) -> Tender | None:
        """Parse a raw g0v API response item into a Tender model.

        Args:
            item: Raw dictionary from API response.

        Returns:
            Parsed Tender or None if parsing fails.
        """
        try:
            tender_id = item.get("id") or item.get("_id", "")
            if not tender_id or not item.get("name"):
                return None

            budget = item.get("price")
            if budget is not None:
                try:
                    budget = float(budget)
                except (ValueError, TypeError):
                    budget = None

            deadline = _parse_date(item.get("endDate") or item.get("end_date"))

            url = item.get("url", "")
            if not url and tender_id:
                url = f"https://pcc.mlwmlw.org/tender/{tender_id}"

            return Tender(
                tender_id=str(tender_id),
                title=item.get("name", ""),
                org_name=item.get("unit") or item.get("org_name", ""),
                procurement_type=item.get("type", ""),
                tender_method=item.get("method", ""),
                budget_amount=budget,
                deadline=deadline,
                url=url,
                category=item.get("category", ""),
                source="g0v",
            )
        except Exception as e:
            logger.debug("Failed to parse g0v tender item: {}", e)
            return None


def _parse_date(value: str | None) -> datetime | None:
    """Attempt to parse a date string in various formats."""
    if not value:
        return None
    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None
