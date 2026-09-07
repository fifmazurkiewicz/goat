"""Tests for `ChatTitleService` — title generation without a real LLM."""

from unittest.mock import AsyncMock

import pytest

from app.domain.chat.title_service import ChatTitleService


@pytest.mark.asyncio
async def test_generate_title_returns_llm_result() -> None:
    llm = AsyncMock()
    llm.complete_json.return_value = {"title": "Plan treningowy na tydzień"}
    svc = ChatTitleService(llm)

    title = await svc._generate_title("Chcę plan na cały tydzień")

    assert title == "Plan treningowy na tydzień"
    llm.complete_json.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_title_empty_returns_none() -> None:
    llm = AsyncMock()
    llm.complete_json.return_value = {"title": "   "}
    svc = ChatTitleService(llm)

    assert await svc._generate_title("Cześć") is None


@pytest.mark.asyncio
async def test_generate_title_truncates_long_title() -> None:
    llm = AsyncMock()
    long_title = "A" * 300
    llm.complete_json.return_value = {"title": long_title}
    svc = ChatTitleService(llm)

    title = await svc._generate_title("Temat")

    assert title is not None
    assert len(title) == 200


@pytest.mark.asyncio
async def test_generate_title_llm_error_returns_none() -> None:
    llm = AsyncMock()
    llm.complete_json.side_effect = RuntimeError("upstream")
    svc = ChatTitleService(llm)

    assert await svc._generate_title("Pytanie") is None
