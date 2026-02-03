"""Abstract base class for tender data sources."""

from abc import ABC, abstractmethod
from datetime import date

from tender_tracker.models import Tender


class TenderSource(ABC):
    """Base class for all tender data sources."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable source name."""

    @abstractmethod
    async def fetch_by_date(self, target_date: date) -> list[Tender]:
        """Fetch tenders published on a specific date.

        Args:
            target_date: The date to query.

        Returns:
            List of tenders found.
        """

    @abstractmethod
    async def search(self, keyword: str) -> list[Tender]:
        """Search tenders by keyword.

        Args:
            keyword: Search keyword.

        Returns:
            List of matching tenders.
        """

    async def close(self) -> None:
        """Clean up resources."""
