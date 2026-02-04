"""ebuying.hinet.net client — CHT joint supply contract e-procurement system."""

import re
from datetime import date, datetime

import httpx
from loguru import logger

from tender_tracker.models import Tender
from tender_tracker.sources.base import TenderSource

BASE_URL = "https://ebuying.hinet.net"
EPVAS_BASE = f"{BASE_URL}/epvas"
RESULTS_PATH = "/epvas/readTenderResults"

# Regex to capture JS objects from resultList.push({...}) calls
_PUSH_RE = re.compile(r"resultList\.push\(\s*(\{[^}]+\})\s*\)", re.DOTALL)
# Regex to extract key-value pairs from a JS object literal
_KV_RE = re.compile(r"""(\w+)\s*:\s*(?:"([^"]*)"|'([^']*)'|(\d[\d,]*\.?\d*))""")

DETAIL_URL_TEMPLATE = f"{EPVAS_BASE}/readTenderDetail?pk={{pk}}"


def _parse_js_objects(html: str) -> list[dict[str, str]]:
    """Extract JS object literals from resultList.push() calls in HTML.

    Args:
        html: Raw HTML containing embedded JavaScript.

    Returns:
        List of parsed dictionaries.
    """
    results: list[dict[str, str]] = []
    for match in _PUSH_RE.finditer(html):
        obj_str = match.group(1)
        obj: dict[str, str] = {}
        for kv in _KV_RE.finditer(obj_str):
            key = kv.group(1)
            value = kv.group(2) or kv.group(3) or kv.group(4) or ""
            obj[key] = value
        if obj:
            results.append(obj)
    return results


def _parse_date(value: str | None) -> datetime | None:
    """Parse date strings in common ebuying formats.

    Args:
        value: Date string like '2026/01/15' or '2026-01-15'.

    Returns:
        Parsed datetime or None.
    """
    if not value:
        return None
    # Strip time portion if present (e.g. "2026-02-04 00:00:00" -> "2026-02-04")
    cleaned = value.strip().split(" ")[0]
    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    return None


def _parse_budget(value: str | None) -> float | None:
    """Parse budget string, stripping commas.

    Args:
        value: Budget string like '1,500,000'.

    Returns:
        Float amount or None.
    """
    if not value:
        return None
    try:
        return float(value.replace(",", ""))
    except (ValueError, TypeError):
        return None


class EbuyingSource(TenderSource):
    """Client for the ebuying.hinet.net e-procurement system."""

    def __init__(
        self,
        *,
        categories: list[str] | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._categories = categories or ["226"]
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            timeout=timeout,
            headers={"User-Agent": "TenderTracker/0.1"},
            follow_redirects=True,
        )

    @property
    def name(self) -> str:
        return "ebuying"

    async def fetch_by_date(self, target_date: date) -> list[Tender]:
        """Fetch tenders by date from ebuying system.

        Fetches all configured categories and filters by ntcDate client-side.

        Args:
            target_date: Date to fetch tenders for.

        Returns:
            List of tenders matching the target date.
        """
        logger.info("Fetching tenders for date {} from ebuying", target_date)
        all_tenders: list[Tender] = []

        for category in self._categories:
            items = await self._fetch_category(category)
            for item in items:
                ntc_date = _parse_date(item.get("ntcDate"))
                if ntc_date and ntc_date.date() == target_date:
                    tender = self._parse_tender(item)
                    if tender:
                        all_tenders.append(tender)

        logger.info("Fetched {} tenders from ebuying for {}", len(all_tenders), target_date)
        return all_tenders

    async def search(self, keyword: str) -> list[Tender]:
        """Search tenders by keyword via ebuying bidName search.

        Args:
            keyword: Search term to match against title or org name.

        Returns:
            List of matching tenders.
        """
        logger.info("Searching ebuying for keyword: {}", keyword)
        try:
            response = await self._client.get(
                RESULTS_PATH,
                params={"searchType": "bidName", "condition": keyword},
            )
            response.raise_for_status()
            items = _parse_js_objects(response.text)
        except httpx.HTTPError as e:
            logger.error("Failed to search ebuying: {}", e)
            items = []
        tenders: list[Tender] = []

        for item in items:
            bid_name = item.get("bidName", "")
            org_name = item.get("orgName", "")
            if keyword in bid_name or keyword in org_name:
                tender = self._parse_tender(item)
                if tender:
                    tenders.append(tender)

        logger.info("Found {} tenders for keyword '{}'", len(tenders), keyword)
        return tenders

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def _fetch_category(self, category: str) -> list[dict[str, str]]:
        """Fetch and parse tenders for a specific category.

        Args:
            category: Category code (e.g. '226', '2*').

        Returns:
            List of raw parsed JS objects.
        """
        try:
            response = await self._client.get(
                RESULTS_PATH,
                params={"searchType": "categoryCode", "condition": category},
            )
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error("Failed to fetch ebuying category {}: {}", category, e)
            return []

        return _parse_js_objects(response.text)

    def _parse_tender(self, item: dict[str, str]) -> Tender | None:
        """Map ebuying JS object fields to Tender model.

        Args:
            item: Parsed JS object dictionary.

        Returns:
            Tender instance or None if required fields are missing.
        """
        try:
            tender_id = item.get("tndCaseNo", "")
            title = item.get("bidName", "")
            if not tender_id or not title:
                return None

            pk = item.get("pk", "")
            url = DETAIL_URL_TEMPLATE.format(pk=pk) if pk else ""

            return Tender(
                tender_id=tender_id,
                title=title,
                org_name=item.get("orgName", ""),
                procurement_type="勞務",
                tender_method="共同供應契約",
                budget_amount=_parse_budget(item.get("budget")),
                deadline=_parse_date(item.get("dueDate")),
                open_date=None,
                url=url,
                category=item.get("catalogName", ""),
                source="ebuying",
                publish_date=_parse_date(item.get("ntcDate")),
            )
        except Exception as e:
            logger.debug("Failed to parse ebuying tender: {}", e)
            return None
