"""mlwmlw/pcc API client — primary real-time data source."""

import asyncio
from datetime import date, datetime

import httpx
from loguru import logger

from tender_tracker.models import Tender
from tender_tracker.sources.base import TenderSource

BASE_URL = "https://pcc.mlwmlw.org/api"
REQUEST_DELAY = 2.0  # seconds between requests


class MlwmlwSource(TenderSource):
    """Client for the mlwmlw PCC API."""

    def __init__(self, *, timeout: float = 30.0) -> None:
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            timeout=timeout,
            headers={"User-Agent": "TenderTracker/0.1"},
        )

    @property
    def name(self) -> str:
        return "mlwmlw"

    async def fetch_by_date(self, target_date: date) -> list[Tender]:
        """Fetch tenders by date from mlwmlw API.

        Args:
            target_date: Date to fetch tenders for.

        Returns:
            List of parsed tenders.
        """
        date_str = target_date.strftime("%Y-%m-%d")
        logger.info("Fetching tenders for date {} from mlwmlw", date_str)

        try:
            response = await self._client.get(f"/date/tender/{date_str}")
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error("Failed to fetch from mlwmlw: {}", e)
            return []

        data = response.json()
        if not isinstance(data, list):
            logger.warning("Unexpected response format from mlwmlw")
            return []

        tenders = [self._parse_tender(item) for item in data if item]
        tenders = [t for t in tenders if t is not None]
        logger.info("Fetched {} tenders from mlwmlw for {}", len(tenders), date_str)
        return tenders

    async def search(self, keyword: str) -> list[Tender]:
        """Search tenders by keyword via mlwmlw API.

        Args:
            keyword: Search term.

        Returns:
            List of matching tenders.
        """
        logger.info("Searching mlwmlw for keyword: {}", keyword)
        await asyncio.sleep(REQUEST_DELAY)

        try:
            response = await self._client.get(f"/keyword/{keyword}")
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error("Failed to search mlwmlw: {}", e)
            return []

        data = response.json()
        if not isinstance(data, list):
            return []

        tenders = [self._parse_tender(item) for item in data if item]
        tenders = [t for t in tenders if t is not None]
        logger.info("Found {} tenders for keyword '{}'", len(tenders), keyword)
        return tenders

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    def _parse_tender(self, item: dict) -> Tender | None:
        """Parse a raw API response item into a Tender model.

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

            publish_date = _parse_date(item.get("publish"))
            deadline = _parse_date(item.get("endDate") or item.get("end_date"))
            open_date = _parse_date(item.get("openDate") or item.get("open_date"))

            url = item.get("url", "")
            if not url and tender_id:
                url = f"https://pcc.mlwmlw.org/tender/{tender_id}"

            return Tender(
                tender_id=str(tender_id),
                title=item.get("name", ""),
                org_name=item.get("unit") or item.get("org_name", ""),
                procurement_type=item.get("category", ""),
                tender_method=item.get("type", ""),
                budget_amount=budget,
                deadline=deadline,
                open_date=open_date,
                url=url,
                category=item.get("sub_category", ""),
                source="mlwmlw",
                publish_date=publish_date,
            )
        except Exception as e:
            logger.debug("Failed to parse tender item: {}", e)
            return None


def _parse_date(value: str | None) -> datetime | None:
    """Attempt to parse a date string in various formats."""
    if not value:
        return None
    # Handle ISO format with timezone (e.g. "2026-01-20T00:00:00.000Z")
    cleaned = value.split("T")[0].strip()
    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    return None
