"""Tender filtering engine with keyword, org, budget, and type filters."""

from loguru import logger

from tender_tracker.config import AppConfig
from tender_tracker.models import Tender


class TenderFilter:
    """Multi-criteria tender filter based on app configuration."""

    def __init__(self, config: AppConfig) -> None:
        self._keywords = [kw.lower() for kw in config.keywords]
        self._orgs = [org.lower() for org in config.orgs]
        self._budget_min = config.budget.min
        self._budget_max = config.budget.max
        self._procurement_types = [pt.lower() for pt in config.procurement_types]

    def filter(self, tenders: list[Tender]) -> list[Tender]:
        """Apply all filters to a list of tenders.

        Args:
            tenders: Raw tender list.

        Returns:
            Tenders that pass all filter criteria.
        """
        results = []
        for tender in tenders:
            if self._matches(tender):
                results.append(tender)

        logger.info(
            "Filtered {} -> {} tenders",
            len(tenders),
            len(results),
        )
        return results

    def keyword_filter(self, tenders: list[Tender]) -> list[Tender]:
        """Filter tenders by keyword match only.

        Args:
            tenders: Raw tender list.

        Returns:
            Tenders matching at least one keyword.
        """
        return [t for t in tenders if self._matches_keyword(t)]

    def _matches(self, tender: Tender) -> bool:
        """Check if a tender matches all configured filter criteria."""
        if not self._matches_keyword(tender):
            return False

        if not self._matches_budget(tender):
            return False

        if not self._matches_procurement_type(tender):
            return False

        return True

    def _matches_keyword(self, tender: Tender) -> bool:
        """Check if tender title or category matches any keyword."""
        if not self._keywords:
            return True

        text = f"{tender.title} {tender.category}".lower()
        return any(kw in text for kw in self._keywords)

    def _matches_org(self, tender: Tender) -> bool:
        """Check if tender organization is in the whitelist."""
        if not self._orgs:
            return True

        org_lower = tender.org_name.lower()
        return any(org in org_lower for org in self._orgs)

    def _matches_budget(self, tender: Tender) -> bool:
        """Check if tender budget is within configured range."""
        if tender.budget_amount is None:
            return True  # Include tenders without budget info

        return self._budget_min <= tender.budget_amount <= self._budget_max

    def _matches_procurement_type(self, tender: Tender) -> bool:
        """Check if tender procurement type matches configured types."""
        if not self._procurement_types:
            return True

        if not tender.procurement_type:
            return True  # Include tenders without type info

        return tender.procurement_type.lower() in self._procurement_types
