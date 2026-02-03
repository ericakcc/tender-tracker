"""Tests for data source clients."""

from datetime import date
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from tender_tracker.sources.mlwmlw import MlwmlwSource


class TestMlwmlwSource:
    """Tests for the mlwmlw API client."""

    @pytest.fixture
    def source(self) -> MlwmlwSource:
        return MlwmlwSource()

    def test_source_name(self, source: MlwmlwSource) -> None:
        assert source.name == "mlwmlw"

    @pytest.mark.asyncio
    async def test_fetch_by_date_success(self, source: MlwmlwSource) -> None:
        mock_data = [
            {
                "id": "T-001",
                "name": "AI 測試標案",
                "unit": "測試機關",
                "type": "勞務",
                "method": "公開招標",
                "price": 500000,
                "endDate": "2026/03/01",
            },
            {
                "id": "T-002",
                "name": "另一個標案",
                "unit": "另一個機關",
                "type": "財物",
                "price": None,
            },
        ]

        mock_response = httpx.Response(
            200, json=mock_data, request=httpx.Request("GET", "https://test")
        )

        with patch.object(
            source._client, "get", new_callable=AsyncMock, return_value=mock_response
        ):
            tenders = await source.fetch_by_date(date(2026, 2, 1))

        assert len(tenders) == 2
        assert tenders[0].tender_id == "T-001"
        assert tenders[0].title == "AI 測試標案"
        assert tenders[0].budget_amount == 500000
        assert tenders[0].source == "mlwmlw"

    @pytest.mark.asyncio
    async def test_fetch_by_date_empty_response(self, source: MlwmlwSource) -> None:
        mock_response = httpx.Response(200, json=[], request=httpx.Request("GET", "https://test"))

        with patch.object(
            source._client, "get", new_callable=AsyncMock, return_value=mock_response
        ):
            tenders = await source.fetch_by_date(date(2026, 2, 1))

        assert tenders == []

    @pytest.mark.asyncio
    async def test_fetch_by_date_http_error(self, source: MlwmlwSource) -> None:
        with patch.object(
            source._client,
            "get",
            new_callable=AsyncMock,
            side_effect=httpx.HTTPStatusError(
                "Server Error",
                request=httpx.Request("GET", "https://test"),
                response=httpx.Response(500),
            ),
        ):
            tenders = await source.fetch_by_date(date(2026, 2, 1))

        assert tenders == []

    @pytest.mark.asyncio
    async def test_search_success(self, source: MlwmlwSource) -> None:
        mock_data = [
            {
                "id": "T-100",
                "name": "AI 系統開發",
                "unit": "數位發展部",
                "type": "勞務",
                "price": 1000000,
            }
        ]

        mock_response = httpx.Response(
            200, json=mock_data, request=httpx.Request("GET", "https://test")
        )

        with patch.object(
            source._client, "get", new_callable=AsyncMock, return_value=mock_response
        ):
            tenders = await source.search("AI")

        assert len(tenders) == 1
        assert tenders[0].tender_id == "T-100"

    @pytest.mark.asyncio
    async def test_parse_tender_missing_id(self, source: MlwmlwSource) -> None:
        result = source._parse_tender({"name": "No ID tender"})
        assert result is None

    @pytest.mark.asyncio
    async def test_parse_tender_missing_name(self, source: MlwmlwSource) -> None:
        result = source._parse_tender({"id": "T-999"})
        assert result is None

    @pytest.mark.asyncio
    async def test_parse_tender_invalid_budget(self, source: MlwmlwSource) -> None:
        result = source._parse_tender(
            {
                "id": "T-999",
                "name": "Test",
                "price": "not_a_number",
            }
        )
        assert result is not None
        assert result.budget_amount is None

    @pytest.mark.asyncio
    async def test_close(self, source: MlwmlwSource) -> None:
        with patch.object(source._client, "aclose", new_callable=AsyncMock) as mock_close:
            await source.close()
            mock_close.assert_called_once()
