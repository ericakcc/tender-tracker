"""Tests for the ebuying.hinet.net data source."""

from datetime import date
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from tender_tracker.sources.ebuying import (
    EbuyingSource,
    _parse_budget,
    _parse_js_objects,
)

MOCK_HTML = (
    "<html><head><script>\nvar resultList = [];\n"
    'resultList.push({tndCaseNo:"EB-2026-001",bidName:"AI 智慧分析平台",'
    'orgName:"數位發展部",budget:"1,500,000",dueDate:"2026/02/15",'
    'ntcDate:"2026/02/01",pk:"abc123",catalogName:"技術服務"});\n'
    'resultList.push({tndCaseNo:"EB-2026-002",bidName:"雲端資料庫維運",'
    'orgName:"經濟部",budget:"800,000",dueDate:"2026/02/20",'
    'ntcDate:"2026/02/01",pk:"def456",catalogName:"資訊服務"});\n'
    'resultList.push({tndCaseNo:"EB-2026-003",bidName:"辦公設備租賃",'
    'orgName:"內政部",budget:"300,000",dueDate:"2026/03/01",'
    'ntcDate:"2026/01/30",pk:"ghi789",catalogName:"設備租賃"});\n'
    "</script></head></html>"
)

MOCK_HTML_MISSING_FIELDS = (
    "<html><script>\nvar resultList = [];\n"
    'resultList.push({tndCaseNo:"",bidName:"No ID tender",'
    'orgName:"TestOrg",ntcDate:"2026/02/01",pk:"x1"});\n'
    'resultList.push({tndCaseNo:"EB-NOID",bidName:"",'
    'orgName:"TestOrg",ntcDate:"2026/02/01",pk:"x2"});\n'
    'resultList.push({tndCaseNo:"EB-VALID",bidName:"Valid Tender",'
    'orgName:"TestOrg",ntcDate:"2026/02/01",pk:"x3"});\n'
    "</script></html>"
)


class TestParseJsObjects:
    """Tests for JavaScript object parsing from HTML."""

    def test_parse_three_entries(self) -> None:
        objects = _parse_js_objects(MOCK_HTML)
        assert len(objects) == 3

    def test_parse_field_values(self) -> None:
        objects = _parse_js_objects(MOCK_HTML)
        first = objects[0]
        assert first["tndCaseNo"] == "EB-2026-001"
        assert first["bidName"] == "AI 智慧分析平台"
        assert first["orgName"] == "數位發展部"
        assert first["budget"] == "1,500,000"
        assert first["pk"] == "abc123"

    def test_parse_empty_html(self) -> None:
        assert _parse_js_objects("<html></html>") == []

    def test_parse_no_push(self) -> None:
        html = "<script>var resultList = [];</script>"
        assert _parse_js_objects(html) == []


class TestParseBudget:
    """Tests for budget string parsing."""

    def test_normal_budget(self) -> None:
        assert _parse_budget("1,500,000") == 1_500_000.0

    def test_no_commas(self) -> None:
        assert _parse_budget("500000") == 500_000.0

    def test_none_value(self) -> None:
        assert _parse_budget(None) is None

    def test_empty_string(self) -> None:
        assert _parse_budget("") is None

    def test_invalid_string(self) -> None:
        assert _parse_budget("not_a_number") is None


class TestEbuyingSource:
    """Tests for the EbuyingSource client."""

    @pytest.fixture
    def source(self) -> EbuyingSource:
        return EbuyingSource(categories=["226"])

    def test_source_name(self, source: EbuyingSource) -> None:
        assert source.name == "ebuying"

    @pytest.mark.asyncio
    async def test_fetch_by_date_success(self, source: EbuyingSource) -> None:
        mock_response = httpx.Response(
            200,
            text=MOCK_HTML,
            request=httpx.Request("GET", "https://test"),
        )

        with patch.object(
            source._client, "get", new_callable=AsyncMock, return_value=mock_response
        ):
            tenders = await source.fetch_by_date(date(2026, 2, 1))

        # Only 2 entries have ntcDate 2026/02/01
        assert len(tenders) == 2
        assert tenders[0].tender_id == "EB-2026-001"
        assert tenders[0].title == "AI 智慧分析平台"
        assert tenders[0].org_name == "數位發展部"
        assert tenders[0].budget_amount == 1_500_000.0
        assert tenders[0].source == "ebuying"
        assert "abc123" in tenders[0].url

    @pytest.mark.asyncio
    async def test_fetch_by_date_filters_by_date(self, source: EbuyingSource) -> None:
        mock_response = httpx.Response(
            200,
            text=MOCK_HTML,
            request=httpx.Request("GET", "https://test"),
        )

        with patch.object(
            source._client, "get", new_callable=AsyncMock, return_value=mock_response
        ):
            tenders = await source.fetch_by_date(date(2026, 1, 30))

        # Only 1 entry has ntcDate 2026/01/30
        assert len(tenders) == 1
        assert tenders[0].tender_id == "EB-2026-003"

    @pytest.mark.asyncio
    async def test_fetch_by_date_no_match(self, source: EbuyingSource) -> None:
        mock_response = httpx.Response(
            200,
            text=MOCK_HTML,
            request=httpx.Request("GET", "https://test"),
        )

        with patch.object(
            source._client, "get", new_callable=AsyncMock, return_value=mock_response
        ):
            tenders = await source.fetch_by_date(date(2025, 12, 25))

        assert tenders == []

    @pytest.mark.asyncio
    async def test_search_keyword_match(self, source: EbuyingSource) -> None:
        mock_response = httpx.Response(
            200,
            text=MOCK_HTML,
            request=httpx.Request("GET", "https://test"),
        )

        with patch.object(
            source._client, "get", new_callable=AsyncMock, return_value=mock_response
        ):
            tenders = await source.search("AI")

        assert len(tenders) == 1
        assert tenders[0].tender_id == "EB-2026-001"

    @pytest.mark.asyncio
    async def test_search_org_match(self, source: EbuyingSource) -> None:
        mock_response = httpx.Response(
            200,
            text=MOCK_HTML,
            request=httpx.Request("GET", "https://test"),
        )

        with patch.object(
            source._client, "get", new_callable=AsyncMock, return_value=mock_response
        ):
            tenders = await source.search("經濟部")

        assert len(tenders) == 1
        assert tenders[0].tender_id == "EB-2026-002"

    @pytest.mark.asyncio
    async def test_search_no_match(self, source: EbuyingSource) -> None:
        mock_response = httpx.Response(
            200,
            text=MOCK_HTML,
            request=httpx.Request("GET", "https://test"),
        )

        with patch.object(
            source._client, "get", new_callable=AsyncMock, return_value=mock_response
        ):
            tenders = await source.search("不存在的關鍵字")

        assert tenders == []

    @pytest.mark.asyncio
    async def test_missing_fields_skipped(self, source: EbuyingSource) -> None:
        mock_response = httpx.Response(
            200,
            text=MOCK_HTML_MISSING_FIELDS,
            request=httpx.Request("GET", "https://test"),
        )

        with patch.object(
            source._client, "get", new_callable=AsyncMock, return_value=mock_response
        ):
            tenders = await source.fetch_by_date(date(2026, 2, 1))

        # Only the valid one should survive
        assert len(tenders) == 1
        assert tenders[0].tender_id == "EB-VALID"

    @pytest.mark.asyncio
    async def test_invalid_budget_handled(self, source: EbuyingSource) -> None:
        html = (
            "<script>\nvar resultList = [];\n"
            'resultList.push({tndCaseNo:"EB-BAD",bidName:"Bad Budget",'
            'orgName:"Org",budget:"abc",ntcDate:"2026/02/01",pk:"z1"});\n'
            "</script>"
        )
        mock_response = httpx.Response(
            200,
            text=html,
            request=httpx.Request("GET", "https://test"),
        )

        with patch.object(
            source._client, "get", new_callable=AsyncMock, return_value=mock_response
        ):
            tenders = await source.fetch_by_date(date(2026, 2, 1))

        assert len(tenders) == 1
        assert tenders[0].budget_amount is None

    @pytest.mark.asyncio
    async def test_http_error_returns_empty(self, source: EbuyingSource) -> None:
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
    async def test_close(self, source: EbuyingSource) -> None:
        with patch.object(source._client, "aclose", new_callable=AsyncMock) as mock_close:
            await source.close()
            mock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_field_mapping(self, source: EbuyingSource) -> None:
        mock_response = httpx.Response(
            200,
            text=MOCK_HTML,
            request=httpx.Request("GET", "https://test"),
        )

        with patch.object(
            source._client, "get", new_callable=AsyncMock, return_value=mock_response
        ):
            tenders = await source.fetch_by_date(date(2026, 2, 1))

        t = tenders[0]
        assert t.procurement_type == "勞務"
        assert t.tender_method == "共同供應契約"
        assert t.category == "技術服務"
        assert t.deadline is not None
        assert t.publish_date is not None
